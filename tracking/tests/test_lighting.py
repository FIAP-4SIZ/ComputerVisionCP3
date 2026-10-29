import copy
from dataclasses import FrozenInstanceError
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from lighting import (DEFAULT_LIGHTING, LightingSettings, apply_lighting,
                      comparison_view, resize_for_pose)
from parameters import Parameters
from test_input_controls import Var
from test_pose_validation import fixture
import inference_gui
import mediapipepose as app


class LightingTests(unittest.TestCase):
    def test_off_is_exact_and_returns_an_independent_writable_copy(self):
        original = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        original.flags.writeable = False
        result = apply_lighting(original)
        np.testing.assert_array_equal(result, original)
        self.assertFalse(np.shares_memory(result, original))
        self.assertTrue(result.flags.writeable)

    def test_manual_example_saturation_and_negative_values_without_abs(self):
        original = np.array([[[80, 200, 255], [0, 10, 20]]], dtype=np.uint8)
        saved = original.copy()
        result = apply_lighting(original, LightingSettings('manual', 1.2, 10))
        np.testing.assert_array_equal(result[0, 0], [106, 250, 255])
        dark = apply_lighting(original, LightingSettings('manual', 1, -100))
        np.testing.assert_array_equal(dark[0, 1], [0, 0, 0])
        np.testing.assert_array_equal(original, saved)

    def test_manual_identity_preserves_every_channel(self):
        original = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
        np.testing.assert_array_equal(apply_lighting(original, LightingSettings('manual')), original)

    def test_equalization_expands_grayscale_luminance_range(self):
        y = np.tile(np.arange(80, 120, dtype=np.uint8), (20, 1))
        original = np.repeat(y[:, :, None], 3, axis=2)
        result = apply_lighting(original, LightingSettings('equalize'))
        self.assertEqual(result.min(), 0)
        self.assertEqual(result.max(), 255)
        np.testing.assert_array_equal(original[:, :, 0], y)

    def test_equalization_changes_only_y_before_conversion_back_to_bgr(self):
        original = np.random.default_rng(5).integers(40, 180, (40, 40, 3), dtype=np.uint8)
        ycrcb = cv2.cvtColor(original, cv2.COLOR_BGR2YCrCb)
        expected = ycrcb.copy()
        expected[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        result = apply_lighting(original, LightingSettings('equalize', 3, 100))
        np.testing.assert_array_equal(result, cv2.cvtColor(expected, cv2.COLOR_YCrCb2BGR))
        # Parâmetros manuais não são empilhados com a equalização.
        np.testing.assert_array_equal(result, apply_lighting(original, LightingSettings('equalize')))

    def test_constant_image_is_not_forced_into_fake_detail(self):
        original = np.full((10, 10, 3), 80, np.uint8)
        np.testing.assert_array_equal(apply_lighting(original, LightingSettings('equalize')), original)

    def test_invalid_settings_and_images(self):
        for kwargs in (dict(mode='automatic'), dict(contrast=0), dict(contrast=4),
                       dict(brightness=101), dict(brightness=-101), dict(contrast=np.nan),
                       dict(brightness=np.inf), dict(contrast=True), dict(compare='yes'), dict(contrast=10**400)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LightingSettings(**kwargs)
        for image in (None, np.zeros((0, 10, 3), np.uint8), np.zeros((2, 2)),
                      np.zeros((2, 2, 4), np.uint8), np.zeros((2, 2, 3), np.float32)):
            with self.assertRaises(ValueError):
                apply_lighting(image)
        with self.assertRaises(ValueError):
            apply_lighting(np.zeros((2, 2, 3), np.uint8), {})

    def test_settings_are_immutable_and_display_toggle_keeps_inference_key(self):
        settings = LightingSettings('manual', 1.2, 20)
        with self.assertRaises(FrozenInstanceError):
            settings.mode = 'off'
        self.assertEqual(settings.inference_key(), LightingSettings('manual', 1.2, 20, True).inference_key())
        self.assertEqual(LightingSettings().inference_key(), LightingSettings('off', 2, 30).inference_key())
        self.assertNotEqual(settings.inference_key(), LightingSettings('manual', 1.3, 20).inference_key())

    def test_comparison_never_draws_on_original_and_preserves_geometry(self):
        original = np.full((120, 160, 3), 80, np.uint8)
        annotated = np.full_like(original, 100)
        result = comparison_view(original, annotated, LightingSettings('manual', compare=True), 1.2)
        self.assertEqual(result.shape, (148, 320, 3))
        np.testing.assert_array_equal(result[28:, :160], original)
        np.testing.assert_array_equal(result[28:, 160:], annotated)
        self.assertFalse(np.shares_memory(result, original))
        self.assertIs(comparison_view(original, annotated, DEFAULT_LIGHTING), annotated)
        with self.assertRaises(ValueError):
            comparison_view(original, annotated[:10], DEFAULT_LIGHTING)
        with self.assertRaises(ValueError):
            comparison_view(original, annotated, {})

    def test_resize_matches_original_pipeline_and_does_not_upscale(self):
        original = np.zeros((720, 1280, 3), np.uint8)
        np.testing.assert_array_equal(resize_for_pose(original, 640), cv2.resize(original, (640, 360)))
        self.assertIs(resize_for_pose(original, 1400), original)
        self.assertEqual(resize_for_pose(np.zeros((1000, 1, 3), np.uint8), 10).shape, (10, 1, 3))
        for size in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                resize_for_pose(original, size)

    def test_parameter_update_is_atomic_and_rejects_invalid_values(self):
        params = Parameters.__new__(Parameters)
        params.lighting = DEFAULT_LIGHTING
        self.assertTrue(params.set_lighting('manual', '1.2', '10', True))
        previous = params.lighting
        for args in (('manual', 'bad', 0, False), ('manual', 1, 'nan', False),
                     ('manual', True, 0, False), ('manual', 1, 0, 'yes'), ('unknown', 1, 0, False)):
            self.assertFalse(params.set_lighting(*args))
            self.assertIs(params.lighting, previous)
        self.assertTrue(params.set_lighting())
        self.assertEqual(params.lighting, DEFAULT_LIGHTING)


class LightingControlTests(unittest.TestCase):
    def test_gui_apply_invalid_input_and_restore(self):
        params = Parameters.__new__(Parameters)
        params.lighting = DEFAULT_LIGHTING
        window = SimpleNamespace(root=Mock(), params=params)
        strings, booleans, entries, buttons = [], [], [], {}
        def variable(target):
            def make(value=None):
                var = Var(value)
                target.append(var)
                return var
            return make
        def entry(*args, **kwargs):
            widget = Mock()
            values = ['']
            widget.insert.side_effect = lambda _, text: values.__setitem__(0, text)
            widget.delete.side_effect = lambda *_: values.__setitem__(0, '')
            widget.get.side_effect = lambda: values[0]
            entries.append(values)
            return widget
        def button(*args, **kwargs):
            buttons[kwargs['text']] = kwargs['command']
            return Mock()
        with ExitStack() as stack:
            for name in ('LabelFrame', 'Frame', 'Label', 'Checkbutton'):
                stack.enter_context(patch.object(inference_gui.tk, name, return_value=Mock()))
            stack.enter_context(patch.object(inference_gui.ttk, 'Combobox', return_value=Mock()))
            stack.enter_context(patch.object(inference_gui.tk, 'StringVar', side_effect=variable(strings)))
            stack.enter_context(patch.object(inference_gui.tk, 'BooleanVar', side_effect=variable(booleans)))
            stack.enter_context(patch.object(inference_gui.tk, 'Entry', side_effect=entry))
            stack.enter_context(patch.object(inference_gui.tk, 'Button', side_effect=button))
            inference_gui.InferenceWindow.make_lighting_controls(window)
            strings[0].set('Brilho e contraste')
            entries[0][0], entries[1][0] = '1.2', '10'
            booleans[0].set(True)
            buttons['Aplicar iluminação']()
            self.assertEqual(params.lighting, LightingSettings('manual', 1.2, 10, True))
            entries[0][0] = 'nan'
            buttons['Aplicar iluminação']()
            self.assertEqual(params.lighting, LightingSettings('manual', 1.2, 10, True))
            self.assertIn('inválidos', strings[1].get())
            buttons['Restaurar original']()
            self.assertEqual(params.lighting, DEFAULT_LIGHTING)


class MainLightingTests(unittest.TestCase):
    def test_original_preserved_bgr_rgb_correct_and_only_input_changes_reset_history(self):
        self.run_main(False)

    def test_camera_pause_can_preview_without_running_pose(self):
        self.run_main(True)

    def run_main(self, paused):
        _, params = fixture()
        params.__dict__.update(webui=False, backend=0, exit_ready=False, model=1,
            min_tracking_confidence=.5, smooth_landmarks=True, static_image=False,
            smoothing=0., additional_smoothing=.7, rotate_image=None, mirror=False,
            maximgsize=640, paused=paused, log_frametime=False, input_mode='camera')
        original = np.zeros((120, 160, 3), np.uint8)
        original[:, :, 2] = 255
        saved = original.copy()
        choices = ([LightingSettings('manual', 1.5, 20, True)] if paused else
                   [DEFAULT_LIGHTING, LightingSettings('manual', 1.5, 20, True), LightingSettings('manual', 1.5, 20)])
        camera = Mock()
        calls = [0]
        def read():
            params.lighting = choices[calls[0]]
            calls[0] += 1
            return original.copy(), .001, float(calls[0])
        camera.read_latest.side_effect = read
        detector = Mock()
        detector.process.return_value = SimpleNamespace(pose_world_landmarks=None, pose_landmarks=None)
        backend = Mock()
        views = []
        def key(_):
            if paused:
                params.exit_ready = True
            return 27 if paused or calls[0] == len(choices) else -1
        with ExitStack() as stack:
            metrics_factory = stack.enter_context(patch.object(app, 'FrameMetrics', wraps=app.FrameMetrics))
            for target, kwargs in (
                ('parameters.Parameters', {'return_value': params}), ('DummyBackend', {'return_value': backend}),
                ('CameraStream', {'return_value': camera}), ('threading.Thread', {}),
                ('mp.solutions.pose.Pose', {'return_value': detector}), ('cv2.namedWindow', {}),
                ('cv2.imshow', {'side_effect': lambda _, image: views.append(image.copy())}),
                ('cv2.destroyAllWindows', {}), ('cv2.waitKey', {'side_effect': key}),
                ('shutdown', {'side_effect': SystemExit}),
            ):
                stack.enter_context(patch.object(app, target, **kwargs) if '.' not in target
                    else patch('mediapipepose.' + target, **kwargs))
            with self.assertRaises(SystemExit):
                app.main()
        np.testing.assert_array_equal(original, saved)
        pair = views[0] if paused else views[1]
        np.testing.assert_array_equal(pair[28:, :160], saved)
        if paused:
            detector.process.assert_not_called()
            self.assertEqual(metrics_factory.call_count, 1)
        else:
            self.assertEqual(detector.process.call_count, 3)
            np.testing.assert_array_equal(detector.process.call_args_list[0].args[0][0, 0], [255, 0, 0])
            np.testing.assert_array_equal(detector.process.call_args_list[1].args[0][0, 0], [255, 20, 20])
            detector.reset.assert_called_once()
            backend.reset.assert_called_once()
            self.assertEqual(metrics_factory.call_count, 2)
        camera.close.assert_called_once()
        detector.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
