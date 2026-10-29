import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / name) for name in ('bin', 'tools')]
import compare_lighting as comparison
from lighting import LightingSettings
from video_source import VideoFileSource, VideoInputError
from test_pose_validation import fixture


class RecordingDetector:
    def __init__(self, result=None, error=None):
        self.images = []
        self.closed = False
        self.result = result or SimpleNamespace(pose_world_landmarks=None)
        self.error = error
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def process(self, image):
        if self.error:
            raise self.error
        self.images.append(image.copy())
        return self.result


class LightingComparisonTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'source.avi'
        self.make_video(self.path)
        self.before = comparison.file_digest(self.path)
        self.detectors = []

    def make_video(self, path, count=3):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 25., (160, 120))
        self.assertTrue(writer.isOpened(), 'Codec MJPG indisponivel; integracao nao validada')
        try:
            for index in range(count):
                frame = np.full((120, 160, 3), 40 + index, np.uint8)
                frame[:, :, 2] = 100 + index
                writer.write(frame)
        finally:
            writer.release()

    def factory(self):
        detector = RecordingDetector()
        self.detectors.append(detector)
        return detector

    def test_same_frames_and_timestamps_with_independent_detectors_and_unchanged_input(self):
        report = comparison.compare_video(self.path, pose_factory=self.factory)
        self.assertEqual(comparison.file_digest(self.path), self.before)
        self.assertTrue(report['input_unchanged'])
        self.assertEqual(len(self.detectors), 3)
        self.assertTrue(all(detector.closed for detector in self.detectors))
        fingerprints = {case['decoded_frames_sha256'] for case in report['cases']}
        self.assertEqual(len(fingerprints), 1)
        for case in report['cases']:
            self.assertEqual(case['frames'], 3)
            self.assertTrue(case['reached_eof'])
            self.assertEqual(case['first_timestamp_ms'], 0)
            self.assertAlmostEqual(case['last_timestamp_ms'], 80)
            self.assertEqual(case['frames_with_pose'], 0)
            self.assertIsNone(case['mean_relevant_visibility'])
            self.assertEqual(case['valid_tracker_frames'], dict(hip=0, right_foot=0, left_foot=0))
        original, manual = report['cases'][:2]
        self.assertGreater(manual['adjusted_image']['mean_luminance'], original['adjusted_image']['mean_luminance'])
        self.assertEqual(original['original_image'], original['adjusted_image'])
        self.assertEqual(original['original_image'], manual['original_image'])

    def test_offline_decoder_can_read_sequentially_without_waiting(self):
        source = VideoFileSource(self.path, clock=lambda: 0., pace=False)
        self.addCleanup(source.close)
        source.start()
        for index in range(3):
            self.assertIsNotNone(source.read_latest())
            self.assertEqual(source.index, index)
            self.assertAlmostEqual(source.timestamp_ms, index * 40.)
        self.assertIsNone(source.read_latest())
        self.assertIsNone(source.cap)
        with self.assertRaises(VideoInputError):
            VideoFileSource(self.path, pace='false')

    def test_frame_limit_and_original_first_variant_are_explicit(self):
        report = comparison.compare_video(self.path, max_frames=1, pose_factory=self.factory)
        self.assertTrue(all(case['frames'] == 1 and not case['reached_eof'] for case in report['cases']))
        for invalid in ([], [LightingSettings('manual')], [None]):
            with self.assertRaises(ValueError):
                comparison.compare_video(self.path, candidates=invalid, pose_factory=self.factory)
        for frames, size in ((-1, 640), (True, 640), (2, 0), (2, 1.5)):
            with self.assertRaises(ValueError):
                comparison.compare_video(self.path, max_frames=frames, max_size=size)

    def test_detection_visibility_and_valid_trackers_are_counted(self):
        landmarks, _ = fixture()
        result = SimpleNamespace(pose_world_landmarks=SimpleNamespace(landmark=landmarks))
        def factory():
            detector = RecordingDetector(result=result)
            self.detectors.append(detector)
            return detector
        report = comparison.compare_video(self.path, pose_factory=factory)
        for case in report['cases']:
            self.assertEqual(case['frames_with_pose'], 3)
            self.assertAlmostEqual(case['mean_relevant_visibility'], .9)
            self.assertEqual(case['valid_tracker_frames'], dict(hip=3, right_foot=3, left_foot=3))

    def test_decoder_and_detector_resources_are_released_after_failure(self):
        sources = []
        def source(*args, **kwargs):
            value = VideoFileSource(*args, **kwargs)
            sources.append(value)
            return value
        detector = RecordingDetector(error=RuntimeError('pose failed'))
        with patch.object(comparison, 'VideoFileSource', side_effect=source):
            with self.assertRaises(RuntimeError):
                comparison.compare_video(self.path, pose_factory=lambda: detector)
        self.assertTrue(detector.closed)
        self.assertIsNone(sources[0].cap)
        self.assertEqual(comparison.file_digest(self.path), self.before)

    def test_changed_input_is_rejected_instead_of_reported_as_fair_comparison(self):
        with patch.object(comparison, 'file_digest', side_effect=['original', 'changed']):
            with self.assertRaisesRegex(RuntimeError, 'alterado'):
                comparison.compare_video(self.path, candidates=(LightingSettings(),), pose_factory=self.factory)

    def test_different_decoded_frames_between_passes_are_rejected(self):
        # Simula um decoder que altera um pixel entre as aberturas do mesmo arquivo.
        calls = [0]
        def source(*args, **kwargs):
            instance = VideoFileSource(*args, **kwargs)
            calls[0] += 1
            if calls[0] == 2:
                read = instance.read_latest
                def changed():
                    packet = read()
                    if packet is not None:
                        packet[0][0, 0] ^= 1
                    return packet
                instance.read_latest = changed
            return instance
        with patch.object(comparison, 'VideoFileSource', side_effect=source):
            with self.assertRaisesRegex(RuntimeError, 'diferentes'):
                comparison.compare_video(self.path, pose_factory=self.factory)

    def test_corrupt_empty_and_missing_files_fail_without_touching_input(self):
        bad = Path(self.directory.name) / 'bad.avi'
        bad.write_bytes(b'not a video')
        for path in (bad, bad.parent / 'missing.avi'):
            with self.assertRaises(ValueError):
                comparison.compare_video(path, pose_factory=self.factory)
        self.assertEqual(bad.read_bytes(), b'not a video')

    def test_cli_never_overwrites_input_or_existing_reports(self):
        output = Path(self.directory.name) / 'report.json'
        output.write_text('keep me')
        for target in (self.path, output):
            with patch.object(comparison, 'compare_video') as compare, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    comparison.main([str(self.path), '--output', str(target)])
                self.assertEqual(exc.exception.code, 2)
                compare.assert_not_called()
        self.assertEqual(output.read_text(), 'keep me')
        self.assertEqual(comparison.file_digest(self.path), self.before)

    def test_cli_creates_a_new_json_only_after_success(self):
        output = Path(self.directory.name) / 'new.json'
        with patch.object(comparison, 'compare_video', return_value={'input_unchanged': True}):
            comparison.main([str(self.path), '--output', str(output)])
        self.assertEqual(json.loads(output.read_text()), {'input_unchanged': True})

    def test_real_mediapipe_comparison_runs_all_passes_on_generated_video(self):
        report = comparison.compare_video(self.path, max_frames=1)
        self.assertEqual(len(report['cases']), 3)
        self.assertTrue(report['input_unchanged'])
        self.assertTrue(all(case['frames'] == 1 for case in report['cases']))
        self.assertTrue(all(case['mean_pose_ms'] > 0 for case in report['cases']))

    def test_unlimited_stream_reports_progress_and_eof(self):
        self.make_video(self.path, count=61)
        progress = []
        result = comparison.compare_video(self.path, max_frames=0, pose_factory=self.factory,
            progress=lambda case, frame: progress.append((case, frame)))
        self.assertEqual(progress, [(0, 60), (1, 60), (2, 60)])
        self.assertTrue(all(case['frames'] == 61 and case['reached_eof'] for case in result['cases']))


if __name__ == '__main__':
    unittest.main()
