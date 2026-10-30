"""Recursos do driver próprio devem manter identidade e contrato nativo."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]/'steamvr'


class DriverResourceTests(unittest.TestCase):
    def test_trigger_profile_exposes_click_and_value_created_by_driver(self):
        path=ROOT/'driver/mediapipe_hands/resources/input/mediapipe_hand_profile.json'
        profile=json.loads(path.read_text(encoding='utf-8'))
        trigger=profile['input_source']['/input/trigger']
        self.assertEqual(trigger['type'],'trigger')
        self.assertIs(trigger['click'],True)
        self.assertIs(trigger['value'],True)

    def test_manifest_and_input_profile_use_own_hand_identity(self):
        driver=ROOT/'driver'/'mediapipe_hands'
        manifest=json.loads((driver/'driver.vrdrivermanifest').read_text(encoding='utf-8'))
        self.assertEqual(manifest['name'],'mediapipe_hands')
        self.assertTrue(manifest['alwaysActivate'])
        profile=json.loads((driver/'resources'/'input'/'mediapipe_hand_profile.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['controller_type'],'fiap_mediapipe_hand')
        for side in ('left','right'):
            source=profile['input_source']['/input/skeleton/'+side]
            self.assertEqual(source['type'],'skeleton')
            self.assertEqual(source['skeleton'],'/skeleton/hand/'+side)

    def test_license_and_sdk_pin_are_preserved(self):
        third=ROOT/'third_party'/'openvr'
        self.assertIn('Valve',(third/'LICENSE').read_text(encoding='utf-8'))
        self.assertIn('0924064316de3effbcd1acf1e309182a2deb1c05',(third/'README.md').read_text(encoding='utf-8'))
