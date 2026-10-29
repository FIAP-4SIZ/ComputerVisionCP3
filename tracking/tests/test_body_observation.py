"""Enquadramento parcial, oclusão e regressões sem câmera física."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from body_observation import observe_body, draw_observation
from inference_gui import InferenceWindow
from test_first_improvement import run_one_frame
import mediapipepose as app


def points():
    return [SimpleNamespace(x=.2+i*.01, y=.3, z=.1, visibility=1.) for i in range(33)]


class BodyObservationTests(unittest.TestCase):
    def test_full_body_and_independent_arms(self):
        p = points()
        self.assertEqual(observe_body(p).framing, 'full')
        p[15].visibility = 0
        self.assertNotIn('left_arm', observe_body(p).groups)
        self.assertIn('right_arm', observe_body(p).groups)

    def test_chest_and_high_visibility_points_outside_image(self):
        p = points()
        for i in range(23, 33):
            p[i].y = 1.2
        result = observe_body(p)
        self.assertEqual(result.framing, 'chest')
        self.assertFalse(set(range(23, 33)) & result.visible)
        self.assertEqual(result.shoulder_angle_degrees, 0.)

    def test_shoulders_only(self):
        p = points()
        for i, point in enumerate(p):
            point.visibility = float(i in (11, 12))
        self.assertEqual(observe_body(p).framing, 'chest')
        self.assertIn('bracos:0/2', observe_body(p).status)

    def test_no_pose_occlusion_and_recovery(self):
        self.assertEqual(observe_body(None).framing, 'none')
        p = points()
        p[11].visibility = 0
        self.assertEqual(observe_body(p).framing, 'lower_body')
        p[11].visibility = 1
        self.assertEqual(observe_body(p).framing, 'full')

    def test_invalid_points(self):
        for field in ('x', 'y', 'z', 'visibility'):
            for value in (float('nan'), float('inf'), None, 'invalid'):
                with self.subTest(field=field, value=value):
                    p = points()
                    setattr(p[11], field, value)
                    self.assertNotIn(11, observe_body(p).visible)
        p = points()
        p[11].visibility = 1.1
        self.assertNotIn(11, observe_body(p).visible)

    def test_threshold_and_boundaries(self):
        p = points()
        p[11].x, p[11].y, p[11].visibility = 0., 1., .5
        self.assertIn(11, observe_body(p).visible)
        self.assertNotIn(11, observe_body(p, .51).visible)
        for value in (-1, 2, float('nan'), True, 'oops'):
            with self.assertRaises(ValueError):
                observe_body(p, value)
        with self.assertRaises(ValueError):
            observe_body(p[:10])

    def test_drawing_with_and_without_detection(self):
        image = np.zeros((64, 64, 3), np.uint8)
        draw_observation(image, None, observe_body(None), {(11, 12)})
        self.assertFalse(image.any())
        p = points()
        p[12].visibility = 0
        draw_observation(image, p, observe_body(p), {(11, 12)})
        self.assertTrue(image.any())

    def test_partial_calibration_message(self):
        window = Mock()
        window.params = SimpleNamespace()
        InferenceWindow.autocalibrate(window)
        self.assertIn('corpo inteiro', window.params.pose_status)
        self.assertFalse(hasattr(window.params, 'pose3d_og'))

    def test_camera_pipeline_regression(self):
        backend = run_one_frame(app, True)
        self.assertTrue(hasattr(backend.test_params, 'body_observation'))
        backend.updatepose.assert_called_once()
