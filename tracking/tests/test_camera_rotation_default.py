"""Não girar a câmera implicitamente; preservar escolhas explícitas salvas."""
import builtins
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from parameters import Parameters

INITIAL = dict(advanced=False, model_complexity=1, smooth_landmarks=True,
    min_tracking_confidence=.5, static_image=False, imgsize=640, camid='0',
    prevskel=False, waithmd=False, feetrot=False, use_hands=False, ignore_hip=False,
    camera_settings=False, camera_height=480, camera_width=640, backend=0,
    backend_ip='127.0.0.1', backend_port=9000, webui=False)


@contextmanager
def isolated_parameters():
    with tempfile.TemporaryDirectory() as directory:
        def local_open(name, *args, **kwargs):
            return builtins.open(Path(directory) / name, *args, **kwargs)
        with patch('parameters.getparams', return_value=INITIAL.copy()), \
             patch('parameters.open', side_effect=local_open, create=True):
            yield Path(directory)


class CameraRotationTests(unittest.TestCase):
    def test_first_run_preserves_camera_orientation(self):
        with isolated_parameters():
            params = Parameters()
        self.assertIsNone(params.rotate_image)
        self.assertEqual(params.img_rot_dict_rev[params.rotate_image], 0)

    def test_each_explicit_rotation_survives_save_and_reload(self):
        with isolated_parameters():
            params = Parameters()
            for index, expected in enumerate((None, cv2.ROTATE_90_CLOCKWISE,
                                               cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE)):
                with self.subTest(index=index):
                    params.change_img_rot(index)
                    params.save_params()
                    restored = Parameters()
                    self.assertEqual(restored.rotate_image, expected)
                    self.assertEqual(restored.img_rot_dict_rev[restored.rotate_image], index)

    def test_saved_ninety_degrees_is_not_silently_discarded(self):
        with isolated_parameters():
            params = Parameters()
            params.change_img_rot(1)
            params.save_params()
            self.assertEqual(Parameters().rotate_image, cv2.ROTATE_90_CLOCKWISE)
            # O usuário pode corrigir uma escolha antiga sem apagar outros ajustes.
            params.change_img_rot(0)
            params.save_params()
            self.assertIsNone(Parameters().rotate_image)

    def test_corrupt_saved_settings_fall_back_to_unrotated_image(self):
        with isolated_parameters() as directory:
            (directory / 'saved_params.json').write_text('invalid json', encoding='utf-8')
            self.assertIsNone(Parameters().rotate_image)
