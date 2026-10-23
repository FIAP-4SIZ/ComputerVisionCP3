"""Testes sem webcam, janela gráfica ou headset: python -m unittest discover -s tests -v."""

import sys
import subprocess
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import ExitStack

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from frame_metrics import FrameMetrics
from helpers import CameraStream
import mediapipepose as app


class MetricsTests(unittest.TestCase):
    def test_fps_uses_whole_cycle_instead_of_pose_only(self):
        metrics = FrameMetrics()
        metrics.add(capture=.02, age=.003, pose=.01, trackers=.005, cycle=.04)
        text = metrics.summary()
        self.assertIn('FPS:25.0', text)  # 1 / 0,04; a fórmula antiga daria ~66,7.
        self.assertIn('pose:10.0ms', text)
        self.assertIn('trackers:5.0ms', text)

    def test_rolling_fps_is_frames_divided_by_elapsed_time(self):
        metrics = FrameMetrics(window=2)
        for seconds in (.1, .02, .06):
            metrics.add(capture=0, age=0, pose=0, trackers=0, cycle=seconds)
        self.assertIn('FPS:25.0', metrics.summary())  # 2 / (0,02 + 0,06).

    def test_empty_and_zero_duration_do_not_divide_by_zero(self):
        metrics = FrameMetrics()
        self.assertIn('primeiro quadro', metrics.summary())
        metrics.add(capture=0, age=0, pose=0, trackers=0, cycle=0)
        self.assertIn('FPS:0.0', metrics.summary())


class CameraTests(unittest.TestCase):
    def make_camera(self, reads):
        camera = CameraStream.__new__(CameraStream)
        camera.params = SimpleNamespace(exit_ready=False)
        camera.frame_lock = threading.Lock()
        camera.image_ready = False
        camera.cap = Mock()
        camera.cap.read.side_effect = reads
        return camera

    def test_failed_read_is_never_published(self):
        for invalid in ((False, None), (True, None), (True, np.empty((0, 0, 3)))):
            with self.subTest(invalid=invalid[0]):
                camera = self.make_camera([invalid])
                camera.update()
                self.assertIsNone(camera.read_latest())
                self.assertTrue(camera.params.exit_ready)
                camera.cap.release.assert_called_once()

    def test_snapshot_keeps_corresponding_time_and_does_not_modify_original(self):
        original = np.full((4, 4, 3), 12, np.uint8)
        camera = self.make_camera([(True, original), (False, None)])
        with patch('helpers.time.perf_counter', side_effect=[1., 1.02, 2., 2.03]):
            camera.update()
        image, duration, timestamp = camera.read_latest()
        self.assertAlmostEqual(duration, .02)
        self.assertEqual(timestamp, 1.02)
        image[:] = 0
        self.assertTrue(np.all(original == 12))
        self.assertIsNone(camera.read_latest())


def run_one_frame(module, with_pose):
    """Executa o laço real; apenas hardware, GUI e inferência são substituídos."""
    original = np.zeros((120, 160, 3), np.uint8)
    original[:, :, 2] = 255  # Vermelho em BGR: deve chegar como [255, 0, 0] ao detector.
    landmarks = [SimpleNamespace(x=i*.01, y=(i % 5)*.1, z=(i % 7)*.04)
                 for i in range(33)]
    result = SimpleNamespace(pose_world_landmarks=SimpleNamespace(landmark=landmarks)
                             if with_pose else None, pose_landmarks=None)
    params = SimpleNamespace(webui=False, backend=2, exit_ready=False, model=1,
                             min_tracking_confidence=.5, smooth_landmarks=True,
                             static_image=False, smoothing=0., additional_smoothing=.7,
                             rotate_image=None, mirror=False, maximgsize=640,
                             paused=False, global_rot_z=Rotation.identity(),
                             global_rot_x=Rotation.identity(), global_rot_y=Rotation.identity(),
                             feet_rotation=False, use_hands=False, log_frametime=True)
    backend = Mock()
    backend.updatepose.return_value = True
    camera = SimpleNamespace(image_ready=True, image_from_thread=original,
                             read_latest=lambda: (original.copy(), .02, module.time.perf_counter()))
    detector = Mock()
    detector.process.return_value = result
    with ExitStack() as stack:
        for target, kwargs in (
            ('parameters.Parameters', {'return_value': params}),
            ('VRChatOSCBackend', {'return_value': backend}),
            ('CameraStream', {'return_value': camera}),
            ('threading.Thread', {}),
            ('mp.solutions.pose.Pose', {'return_value': detector}),
            ('cv2.namedWindow', {}), ('cv2.imshow', {}),
            ('cv2.waitKey', {'return_value': 27}),
            ('shutdown', {'side_effect': SystemExit}),
        ):
            stack.enter_context(patch.object(module, target, **kwargs) if '.' not in target
                                else patch(module.__name__ + '.' + target, **kwargs))
        try:
            module.main()
        except SystemExit:
            pass
    np.testing.assert_array_equal(detector.process.call_args.args[0][0, 0], [255, 0, 0])
    np.testing.assert_array_equal(original[0, 0], [0, 0, 255])
    return backend


class MainLoopTests(unittest.TestCase):
    def test_pose_reaches_backend_and_exit_still_works(self):
        backend = run_one_frame(app, with_pose=True)
        backend.updatepose.assert_called_once()
        self.assertEqual(backend.updatepose.call_args.args[1].shape, (29, 3))
        self.assertTrue(np.isfinite(backend.updatepose.call_args.args[1]).all())
        backend.disconnect.assert_called_once()

    def test_no_pose_does_not_update_trackers(self):
        backend = run_one_frame(app, with_pose=False)
        backend.updatepose.assert_not_called()
        backend.disconnect.assert_called_once()


class OriginalComparisonTests(unittest.TestCase):
    def test_tracker_inputs_equal_original_for_identical_landmarks(self):
        source = (Path(__file__).parent / 'fixtures/original_mediapipepose.py').read_text()
        original = types.ModuleType('original_app')
        with patch.dict(sys.modules, original_app=original):
            exec(compile(source, 'original/mediapipepose.py', 'exec'), original.__dict__)
            before = run_one_frame(original, True).updatepose.call_args.args
        after = run_one_frame(app, True).updatepose.call_args.args
        np.testing.assert_array_equal(before[1], after[1])
        for old_rotation, new_rotation in zip(before[2], after[2]):
            np.testing.assert_array_equal(old_rotation, new_rotation)


if __name__ == '__main__':
    unittest.main()
