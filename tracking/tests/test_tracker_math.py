"""Regressão contra resultados congelados do commit 968bbf1."""
import json
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from helpers import get_rot, get_rot_mediapipe, get_rot_hands


class TrackerMathTests(unittest.TestCase):
    def test_rotations_match_frozen_original_including_straight_leg_fallback(self):
        data = json.loads((Path(__file__).parent / 'fixtures/rotations_reference.json').read_text())
        pose = np.array(data['pose'])
        for function, key in ((get_rot, 'legs'), (get_rot_mediapipe, 'feet'), (get_rot_hands, 'hands')):
            np.testing.assert_allclose(function(pose), data[key], rtol=0, atol=1e-12)
        pose[4] = (pose[3] + pose[5]) / 2
        np.testing.assert_allclose(get_rot(pose), data['straight_left_leg'], rtol=0, atol=1e-12)
        for key, indices in (('straight_right_leg', (1,)), ('straight_both_legs', (1, 4))):
            pose = np.array(data['pose'])
            for index in indices:
                hip, ankle = (2, 0) if index == 1 else (3, 5)
                pose[index] = (pose[hip] + pose[ankle]) / 2
            np.testing.assert_allclose(get_rot(pose), data[key], rtol=0, atol=1e-12)


if __name__ == '__main__':
    unittest.main()
