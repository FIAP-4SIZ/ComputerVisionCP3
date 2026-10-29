import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from body_observation import observe_body
from independent_trackers import prepare_trackers
from hand_quality import HandQualitySettings
from finger_tracking import FingerTracking
from parameters import Parameters
from test_pose_validation import fixture
from test_finger_tracking import detection, empty
from unittest.mock import Mock


def image_points():
    return [NS(x=.5,y=.5,z=0.,visibility=.9) for _ in range(33)]


class ObservedTrackerTests(unittest.TestCase):
    def test_outside_image_overrules_high_world_visibility(self):
        world, params = fixture()
        original = copy.deepcopy(world)
        image = image_points()
        self.assertTrue(all(prepare_trackers(world,params,image).valid.values()))
        image[27].y = 1.5
        frame = prepare_trackers(world,params,image)
        self.assertTrue(frame.valid['hip'])
        self.assertTrue(frame.valid['right_foot'])
        self.assertFalse(frame.valid['left_foot'])
        self.assertIsNone(frame.calibration)
        self.assertEqual(vars(world[27]),vars(original[27]))

    def test_no_image_does_not_turn_world_estimates_into_observations(self):
        world, params = fixture()
        self.assertFalse(any(prepare_trackers(world,params,None).valid.values()))
        params.min_visibility = 0
        self.assertFalse(any(prepare_trackers(world,params,None).valid.values()))

    def test_seated_crop_chest_one_arm_head_and_lower_body(self):
        cases = [((11,12,23,24),'trunk'), ((11,12),'chest'),
                 ((11,13,15),'arms'), ((0,7,8),'head'),
                 ((23,24,25,27),'lower_body')]
        for indices, label in cases:
            image = image_points()
            for i,p in enumerate(image):
                p.visibility = .9 if i in indices else 0
            self.assertEqual(observe_body(image).framing,label)

    def test_image_visibility_and_nonfinite_points_are_gates(self):
        for field,value in (('visibility',.1),('x',float('nan')),('x',-1)):
            world,params = fixture()
            image = image_points()
            setattr(image[27],field,value)
            self.assertFalse(prepare_trackers(world,params,image).valid['left_foot'])

    def test_complete_image_preserves_original_transforms(self):
        world,params = fixture()
        old,new = prepare_trackers(world,params),prepare_trackers(world,params,image_points())
        np.testing.assert_array_equal(old.pose,new.pose)
        np.testing.assert_array_equal(old.rotations,new.rotations)


class HandQualityTests(unittest.TestCase):
    def make(self, **options):
        detector = Mock()
        detector.process.return_value = detection()
        return FingerTracking(detector,settings=HandQualitySettings(**options))

    def test_one_frame_detection_waits_then_confirms(self):
        tracker = self.make()
        image = np.zeros((480,640,3),np.uint8)
        self.assertEqual(tracker.process(image),{})
        self.assertIn('Left',tracker.process(image))
        tracker.detector.process.return_value = empty()
        self.assertEqual(tracker.process(image),{})
        tracker.detector.process.return_value = detection()
        self.assertEqual(tracker.process(image),{})
        self.assertIn('Left',tracker.process(image))

    def test_tiny_and_collapsed_palms_are_not_sent(self):
        tracker = self.make(confirmation_frames=1)
        self.assertEqual(tracker.process(np.zeros((16,16,3),np.uint8)),{})
        result = detection()
        for p in result.multi_hand_landmarks[0].landmark:
            p.x = .5
        tracker.detector.process.return_value = result
        self.assertEqual(tracker.process(np.zeros((480,640,3),np.uint8)),{})

    def test_implausible_segment_length_and_bad_classification(self):
        tracker = self.make(confirmation_frames=1)
        result = detection()
        result.multi_hand_world_landmarks[0].landmark[4].z = 100
        tracker.detector.process.return_value = result
        self.assertEqual(tracker.process(np.zeros((480,640,3),np.uint8)),{})
        for score in (None,'invalid',float('inf')):
            result = detection()
            result.multi_handedness[0].classification[0].score = score
            tracker.detector.process.return_value = result
            self.assertFalse(tracker.process(np.zeros((480,640,3),np.uint8)))

    def test_large_jump_reconfirms_instead_of_freezing_forever(self):
        tracker = self.make(max_step_palms=.5)
        image = np.zeros((480,640,3),np.uint8)
        tracker.process(image)
        self.assertTrue(tracker.process(image))
        result = detection()
        for p in result.multi_hand_landmarks[0].landmark:
            p.x += .3
        tracker.detector.process.return_value = result
        self.assertFalse(tracker.process(image))
        self.assertTrue(tracker.process(image))

    def test_mirror_or_setting_changes_reconfirm(self):
        tracker = self.make()
        image = np.zeros((480,640,3),np.uint8)
        tracker.process(image)
        self.assertTrue(tracker.process(image))
        self.assertFalse(tracker.process(image,mirrored=True))
        self.assertTrue(tracker.process(image,mirrored=True))
        tracker.settings = HandQualitySettings(confirmation_frames=3)
        self.assertFalse(tracker.process(image,mirrored=True))
        tracker.detector.reset.assert_called()

    def test_settings_invalid_values_and_parameter_callback(self):
        params = Parameters.__new__(Parameters)
        params.hand_quality = HandQualitySettings()
        self.assertTrue(params.set_hand_quality('.8','15','3','2'))
        previous = params.hand_quality
        for args in ((True,10,2,2),('.4',10,2,2),(.8,-1,2,2),(.8,10,1.5,2),(.8,10,2,float('nan'))):
            self.assertFalse(params.set_hand_quality(*args))
            self.assertEqual(params.hand_quality,previous)
        for opts in ({'confirmation_frames':True},{'min_palm_pixels':float('nan')},{'max_step_palms':0}):
            with self.assertRaises(ValueError):
                HandQualitySettings(**opts)
