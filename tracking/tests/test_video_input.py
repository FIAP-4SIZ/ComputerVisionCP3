import math
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import mediapipe as mp
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from video_source import VideoFileSource, VideoInputError
from backends import DummyBackend
from test_first_improvement import run_one_frame
import mediapipepose as app


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'test.avi'
        self.path.touch()
        self.now = 0.

    def source(self, frames=None, fps=25., total=3, timestamps=None, opened=True):
        if frames is None:
            frames = [np.full((20, 30, 3), i, np.uint8) for i in range(3)]
        cap = Mock()
        cap.isOpened.return_value = opened
        cap.read.side_effect = [(True, frame) for frame in frames] + [(False, None)]
        def get(prop):
            if prop == cv2.CAP_PROP_FPS:
                return fps
            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return total
            i = cap.read.call_count - 1
            return timestamps[i] if timestamps else i * 40.
        cap.get.side_effect = get
        with patch('video_source.cv2.VideoCapture', return_value=cap):
            source = VideoFileSource(self.path, clock=lambda: self.now)
        self.addCleanup(source.close)
        return source, cap

    def test_missing_path_directory_and_unsupported_format(self):
        for path in (self.path.parent, self.path.parent/'missing.avi'):
            with self.assertRaises(VideoInputError):
                VideoFileSource(path)
        other = self.path.with_suffix('.txt')
        other.touch()
        with self.assertRaises(VideoInputError):
            VideoFileSource(other)

    def test_cannot_decode_releases_capture(self):
        cap = Mock()
        cap.isOpened.return_value = False
        with patch('video_source.cv2.VideoCapture', return_value=cap):
            with self.assertRaises(VideoInputError):
                VideoFileSource(self.path)
        cap.release.assert_called_once()

    def test_invalid_fps(self):
        for fps in (0, -1, math.nan, math.inf):
            with self.subTest(fps=fps), self.assertRaises(VideoInputError):
                self.source(fps=fps)

    def test_empty_file_and_invalid_first_frames(self):
        for frames in ([], [None], [np.empty((0, 0, 3))], [np.zeros((20, 20))]):
            with self.subTest(frames=len(frames)), self.assertRaises(VideoInputError):
                self.source(frames=frames)

    def test_sequence_progress_timestamps_and_eof_release(self):
        source, cap = self.source()
        self.assertIsNone(source.read_latest())  # pronto, ainda não iniciado
        source.start()
        for index in range(3):
            self.now = index
            image, duration, _ = source.read_latest()
            self.assertTrue(np.all(image == index))
            self.assertEqual(source.index, index)
            self.assertEqual(source.timestamp_ms, index * 40)
            self.assertGreaterEqual(duration, 0)
        self.assertIn('100.0%', source.status)
        self.assertIsNone(source.read_latest())
        self.assertEqual(source.state, 'completed')
        source.close()
        cap.release.assert_called_once()

    def test_pause_resume_does_not_decode_or_skip_and_preserves_remaining_wait(self):
        source, cap = self.source()
        source.start()
        source.read_latest()
        self.now = .01
        source.pause()
        self.now = 10.
        calls = cap.read.call_count
        self.assertIsNone(source.read_latest())
        self.assertEqual(cap.read.call_count, calls)
        source.start()
        self.assertIsNone(source.read_latest())
        self.now = 10.04
        self.assertIsNotNone(source.read_latest())
        self.assertEqual(source.index, 1)

    def test_cancel_and_restart_reset_position(self):
        source, cap = self.source()
        source.start()
        source.read_latest()
        source.cancel()
        self.assertIsNone(source.read_latest())
        self.assertEqual(source.state, 'cancelled')
        cap.release.assert_called_once()
        other, second = self.source()
        other.close()
        second.reset_mock()
        second.read.side_effect = [(True, np.zeros((20, 30, 3), np.uint8)), (False, None)]
        with patch('video_source.cv2.VideoCapture', return_value=second):
            source.restart()
        self.assertEqual(source.state, 'running')
        self.assertEqual(source.index, -1)
        self.assertIsNotNone(source.read_latest())
        self.assertEqual(source.index, 0)

    def test_variable_timestamps_and_invalid_timestamp_fallback(self):
        for timestamps, expected in (([0, 50, 120], [0, 50, 120]),
                                     ([0, 0, math.nan], [0, 40, 80]),
                                     ([0, 100, 50], [0, 100, 140])):
            source, _ = self.source(timestamps=timestamps)
            source.start()
            for timestamp in expected:
                self.now += 1
                self.assertIsNotNone(source.read_latest())
                self.assertAlmostEqual(source.timestamp_ms, timestamp)
            self.assertEqual(source.timestamp_estimated, timestamps[-1] != expected[-1])

    def test_one_pending_frame_and_no_decode_until_due(self):
        source, cap = self.source(total=100000)
        self.assertEqual(cap.read.call_count, 1)
        source.start()
        source.read_latest()
        self.assertIsNone(source.read_latest())
        self.assertIsNone(source.read_latest())
        self.assertEqual(cap.read.call_count, 2)

    def test_truncated_stream_invalid_frame_and_decoder_exception(self):
        for failure in ((False, None), (True, None), RuntimeError('decoder failed')):
            source, cap = self.source()
            source.start()
            source.read_latest()
            cap.read.side_effect = [failure]
            self.now = 1
            with self.assertRaises(VideoInputError):
                source.read_latest()
            self.assertEqual(source.state, 'error')
            self.assertIsNone(source.cap)

    def test_unknown_count_finishes_without_false_corruption(self):
        source, _ = self.source(total=0)
        source.start()
        for i in range(4):
            self.now = i
            source.read_latest()
        self.assertEqual(source.state, 'completed')
        self.assertIn('/?', source.status)

    def test_analysis_only_backend_keeps_existing_pipeline(self):
        self.assertTrue(DummyBackend().updatepose(None, None, None, None))
        backend = run_one_frame(app, True)
        backend.updatepose.assert_called_once()


class RealVideoIntegrationTests(unittest.TestCase):
    def test_main_loop_real_video_pose_and_resource_cleanup(self):
        self.run_real_main('normal')

    def test_main_loop_pose_failure_releases_resources(self):
        self.run_real_main('pose-error')

    def test_main_loop_pause_resume_restart_and_cancel(self):
        self.run_real_main('controls')

    def test_pause_arriving_after_read_does_not_drop_a_frame(self):
        self.run_real_main('pause-boundary')

    def run_real_main(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'application.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 25., (160, 120))
            self.assertTrue(writer.isOpened())
            for _ in range(3):
                writer.write(np.zeros((120, 160, 3), np.uint8))
            writer.release()
            source = VideoFileSource(path)
            params = SimpleNamespace(webui=False, backend=0, exit_ready=False, model=1,
                min_tracking_confidence=.5, smooth_landmarks=True, static_image=False,
                smoothing=0., additional_smoothing=.7, rotate_image=None, mirror=False,
                maximgsize=640, paused=False, feet_rotation=False, use_hands=False,
                log_frametime=False, input_mode='video', video_path=str(path),
                restart_input=False, cancel_input=False, input_status='')
            detector = mp.solutions.pose.Pose(model_complexity=1)
            real_process = detector.process
            timestamps = []
            original_read = source.read_latest
            injected_pause = [False]
            def read_with_pause():
                packet = original_read()
                if mode == 'pause-boundary' and packet is not None and not injected_pause[0]:
                    params.paused = True
                    injected_pause[0] = True
                return packet
            def process(image):
                timestamps.append(params.frame_timestamp_ms)
                if mode == 'pose-error':
                    raise RuntimeError('inference failure')
                if mode == 'controls':
                    if len(timestamps) == 1:
                        params.paused = True
                    elif len(timestamps) == 2:
                        params.restart_input = True
                    else:
                        params.cancel_input = True
                return real_process(image)
            ticks = [0]
            def key(_):
                ticks[0] += 1
                if ticks[0] > 2000:
                    raise AssertionError('O fluxo de vídeo não finalizou')
                if source.state == 'paused':
                    params.paused = False
                return 27 if source.state in ('completed', 'error', 'cancelled') else -1
            backend = Mock(wraps=DummyBackend())
            with ExitStack() as stack:
                for target, kwargs in (
                    ('parameters.Parameters', {'return_value': params}),
                    ('DummyBackend', {'return_value': backend}),
                    ('VideoFileSource', {'return_value': source}),
                    ('threading.Thread', {}),
                    ('inference_gui.create_inference_gui', {'return_value': Mock()}),
                    ('mp.solutions.pose.Pose', {'return_value': detector}),
                    ('cv2.namedWindow', {}), ('cv2.imshow', {}), ('cv2.destroyAllWindows', {}),
                    ('cv2.waitKey', {'side_effect': key}), ('shutdown', {'side_effect': SystemExit}),
                ):
                    stack.enter_context(patch.object(app, target, **kwargs) if '.' not in target
                        else patch('mediapipepose.' + target, **kwargs))
                stack.enter_context(patch.object(detector, 'process', side_effect=process))
                stack.enter_context(patch.object(source, 'read_latest', side_effect=read_with_pause))
                with self.assertRaises(SystemExit):
                    app.main()
            expected = {'normal': [0, 40, 80], 'pose-error': [0], 'controls': [0, 40, 0],
                        'pause-boundary': [0, 40, 80]}
            np.testing.assert_allclose(timestamps, expected[mode])
            self.assertEqual(source.state, {'normal': 'completed', 'pause-boundary': 'completed', 'pose-error': 'error',
                                           'controls': 'cancelled'}[mode])
            backend.updatepose.assert_not_called()  # Vídeo vazio não deve inventar trackers.
            backend.disconnect.assert_called_once()
            self.assertIsNone(source.cap)

    def test_opencv_decoding_and_real_legacy_mediapipe_no_person(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'generated.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 25., (160, 120))
            self.assertTrue(writer.isOpened(), 'Codec MJPG indisponível: integração não validada')
            try:
                for intensity in (0, 30, 60):
                    writer.write(np.full((120, 160, 3), intensity, np.uint8))
            finally:
                writer.release()
            now = [0.]
            source = VideoFileSource(path, clock=lambda: now[0])
            self.addCleanup(source.close)
            source.start()
            with mp.solutions.pose.Pose(model_complexity=1) as detector:
                for index in range(3):
                    now[0] = index
                    frame = source.read_latest()[0]
                    result = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    self.assertIsNone(result.pose_world_landmarks)
                    self.assertEqual(source.index, index)
                    self.assertAlmostEqual(source.timestamp_ms, index * 40.)
            self.assertIsNone(source.read_latest())
            self.assertEqual(source.state, 'completed')
            self.assertIsNone(source.cap)


if __name__ == '__main__':
    unittest.main()
