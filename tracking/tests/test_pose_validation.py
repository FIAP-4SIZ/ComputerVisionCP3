import copy
import sys
import tempfile
import builtins
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from pythonosc.osc_packet import OscPacket
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from pose_validation import InvalidPose, prepare_pose, valid_tracker_data
from backends import VRChatOSCBackend, SteamVRBackend
from parameters import Parameters
from inference_gui import InferenceWindow
import mediapipepose as app
from test_first_improvement import run_one_frame


def fixture():
    rng = np.random.default_rng(42)
    landmarks = [SimpleNamespace(x=x, y=y, z=z, visibility=.9)
                 for x, y, z in rng.normal(size=(33, 3))]
    params = SimpleNamespace(min_visibility=.5, feet_rotation=False, use_hands=False,
        preview_skeleton=False, global_rot_z=Rotation.identity(),
        global_rot_x=Rotation.identity(), global_rot_y=Rotation.identity())
    return landmarks, params


class LandmarkValidationTests(unittest.TestCase):
    def test_threshold_save_and_load_uses_runtime_parameters(self):
        initial = dict(advanced=False, model_complexity=1, smooth_landmarks=True,
            min_tracking_confidence=.5, static_image=False, imgsize=640, camid='0',
            prevskel=False, waithmd=False, feetrot=False, use_hands=False, ignore_hip=False,
            camera_settings=False, camera_height=480, camera_width=640, backend=0,
            backend_ip='127.0.0.1', backend_port=9000, webui=False)
        with tempfile.TemporaryDirectory() as directory:
            def local_open(name, *args, **kwargs):
                return builtins.open(Path(directory) / name, *args, **kwargs)
            with patch('parameters.getparams', return_value=initial), \
                 patch('parameters.open', side_effect=local_open, create=True):
                params = Parameters()
                params.set_min_visibility(.7)
                params.set_tracker_timeout(.2)
                params.save_params()
                restored = Parameters()
        self.assertEqual(restored.min_visibility, .7)
        self.assertEqual(restored.tracker_timeout, .2)

    def test_valid_pose_retains_all_positions_and_quaternions(self):
        landmarks, params = fixture()
        pose, calibration, rotations, hands = prepare_pose(landmarks, params)
        self.assertEqual(pose.shape, (29, 3))
        self.assertTrue(valid_tracker_data(pose, rotations, hands))
        np.testing.assert_array_equal(pose, calibration)
        self.assertIsNone(hands)

    def test_invalid_lengths_missing_attributes_and_nonfinite_coordinates(self):
        landmarks, params = fixture()
        for bad in (None, 3, [], landmarks[:-1], [SimpleNamespace()] * 33):
            with self.subTest(case=str(type(bad))), self.assertRaises(InvalidPose):
                prepare_pose(bad, params)
        for value in (np.nan, np.inf, -np.inf, 'invalid', None):
            bad = copy.deepcopy(landmarks)
            bad[27].x = value
            with self.subTest(value=value), self.assertRaises(InvalidPose):
                prepare_pose(bad, params)

    def test_occluded_ankle_and_visibility_errors(self):
        for value in (.49, -.1, 1.1, np.nan, np.inf, None, 'invalid'):
            landmarks, params = fixture()
            landmarks[27].visibility = value
            with self.subTest(value=value), self.assertRaises(InvalidPose):
                prepare_pose(landmarks, params)
        landmarks, params = fixture()
        del landmarks[27].visibility
        with self.assertRaises(InvalidPose):
            prepare_pose(landmarks, params)

    def test_visibility_boundary_and_threshold_validation(self):
        landmarks, params = fixture()
        landmarks[27].visibility = .5
        prepare_pose(landmarks, params)
        for value in (-1, 2, np.nan, np.inf, 'bad', None):
            params.min_visibility = value
            with self.subTest(value=value), self.assertRaises(InvalidPose):
                prepare_pose(landmarks, params)

    def test_only_required_visible_points_depend_on_enabled_features(self):
        landmarks, params = fixture()
        landmarks[31].visibility = 0
        prepare_pose(landmarks, params)
        params.feet_rotation = True
        with self.assertRaises(InvalidPose):
            prepare_pose(landmarks, params)
        landmarks, params = fixture()
        landmarks[17].visibility = 0
        prepare_pose(landmarks, params)
        params.use_hands = True
        with self.assertRaises(InvalidPose):
            prepare_pose(landmarks, params)
        params.use_hands = False
        params.preview_skeleton = True
        with self.assertRaises(InvalidPose):
            prepare_pose(landmarks, params)

    def test_degenerate_geometry_rejected(self):
        landmarks, params = fixture()
        for point in landmarks:
            point.x = point.y = point.z = 0
        with self.assertRaises(InvalidPose):
            prepare_pose(landmarks, params)
        params.feet_rotation = True
        with self.assertRaises(InvalidPose):
            prepare_pose(landmarks, params)

    def test_hands_feet_and_large_real_movements_are_not_filtered_by_speed(self):
        landmarks, params = fixture()
        params.feet_rotation = params.use_hands = True
        pose, _, rotations, hands = prepare_pose(landmarks, params)
        self.assertTrue(valid_tracker_data(pose, rotations, hands))
        for point in landmarks:
            point.x += 100
        moved, _, _, _ = prepare_pose(landmarks, params)
        self.assertGreater(np.max(np.abs(moved - pose)), 50)

    def test_threshold_ui_keeps_previous_valid_value_on_error(self):
        params = Parameters.__new__(Parameters)
        params.min_visibility = .5
        self.assertTrue(params.set_min_visibility('0.7'))
        for value in ('bad', np.nan, 2, -1, None):
            self.assertFalse(params.set_min_visibility(value))
            self.assertEqual(params.min_visibility, .7)
        self.assertTrue(params.set_min_visibility(0))
        self.assertTrue(params.set_min_visibility(1))

    def test_no_valid_pose_prevents_calibration_even_with_tilt_disabled(self):
        window = Mock()
        window.params = SimpleNamespace(backend=1, calib_tilt=False, calib_rot=True)
        with patch('inference_gui.sendToSteamVR') as send:
            InferenceWindow.autocalibrate(window)
        send.assert_not_called()

    def test_main_rejects_invalid_pose_without_updating_backend(self):
        with patch.object(app, 'prepare_trackers', side_effect=InvalidPose('occluded')):
            backend = run_one_frame(app, with_pose=True)
        backend.updatepose.assert_not_called()
        backend.disconnect.assert_called_once()

    def test_lost_pose_removes_cached_calibration(self):
        backend = run_one_frame(app, with_pose=False, existing_calibration=True)
        self.assertFalse(hasattr(backend.test_params, 'pose3d_og'))
        backend.updatepose.assert_not_called()


class OSCValidationTests(unittest.TestCase):
    def setUp(self):
        self.backend = VRChatOSCBackend()
        self.backend.client = Mock()
        self.params = SimpleNamespace(additional_smoothing=.7, hmd_to_neck_offset=[0, -.2, .1],
            recalibrate=False, posescale=1., preview_skeleton=False, ignore_hip=False, use_hands=False,
            camera_latency=0)
        self.pose = np.ones((29, 3))
        self.rotations = np.tile([0., 0., 0., 1.], (3, 1))

    def test_first_valid_frame_seeds_history_and_existing_filter_is_preserved(self):
        self.assertTrue(self.backend.updatepose(self.params, self.pose, self.rotations, None))
        np.testing.assert_array_equal(self.backend.history['hip'], self.pose[[6, 7]])
        self.assertTrue(self.backend.updatepose(self.params, self.pose * 2, self.rotations, None))
        np.testing.assert_allclose(self.backend.history['hip'], self.pose[[6, 7]] * 1.3)
        np.testing.assert_array_equal(self.pose, np.ones((29, 3)))
        bundle = self.backend.client.send.call_args.args[0]
        messages = OscPacket(bundle.dgram).messages
        expected = {'/tracking/trackers/head/position'} | {
            f'/tracking/trackers/{i}/{field}' for i in (1, 2, 3) for field in ('position', 'rotation')}
        self.assertEqual({item.message.address for item in messages}, expected)
        self.assertTrue(all(np.isfinite(item.message.params).all() for item in messages))

    def test_invalid_frame_does_not_contaminate_history_or_send_messages(self):
        self.backend.updatepose(self.params, self.pose, self.rotations, None)
        previous = {name: pair.copy() for name, pair in self.backend.history.items()}
        for pose, rotations in ((np.full((29, 3), np.nan), self.rotations),
                                (np.zeros((3, 3)), self.rotations),
                                (self.pose, np.zeros((3, 4))),
                                (self.pose, np.full((3, 4), np.inf))):
            self.assertFalse(self.backend.updatepose(self.params, pose, rotations, None))
        for name, pair in previous.items():
            np.testing.assert_array_equal(pair, self.backend.history[name])
        self.backend.client.send.assert_called_once()

    def test_smoothing_invalid_boundaries_and_reset(self):
        for value in (-1, 2, np.nan, np.inf, 'bad', None):
            self.params.additional_smoothing = value
            self.assertFalse(self.backend.updatepose(self.params, self.pose, self.rotations, None))
        self.assertEqual(self.backend.history, {})
        for value in (0, 1):
            self.params.additional_smoothing = value
            self.assertTrue(self.backend.updatepose(self.params, self.pose, self.rotations, None))
        self.backend.reset()
        self.assertEqual(self.backend.history, {})

    def test_tracker_data_rejects_invalid_hands_and_unnormalized_quaternion(self):
        self.assertFalse(valid_tracker_data(self.pose, self.rotations * 2))
        self.assertFalse(valid_tracker_data(self.pose, self.rotations, np.zeros((2, 4))))
        self.assertFalse(valid_tracker_data(self.pose, self.rotations, np.full((2, 4), np.nan)))
        self.assertFalse(valid_tracker_data('invalid', 'invalid'))

    def test_invalid_alignment_is_not_sent_to_either_backend(self):
        for scale, offset in ((np.nan, [0, 0, 0]), (-1, [0, 0, 0]),
                              (1, [0, np.inf, 0]), (1, [0, 0])):
            self.params.posescale = scale
            self.params.hmd_to_neck_offset = offset
            self.assertFalse(self.backend.updatepose(self.params, self.pose, self.rotations, None))
            with patch('backends.sendToSteamVR') as send:
                self.assertFalse(SteamVRBackend().updatepose(self.params, self.pose, self.rotations, None))
                send.assert_not_called()
        self.backend.client.send.assert_not_called()
        self.params.posescale = '1.0'
        self.params.hmd_to_neck_offset = ['0', '-.2', '.1']
        self.assertTrue(self.backend.updatepose(self.params, self.pose, self.rotations, None))

    def test_valid_steamvr_messages_keep_existing_protocol(self):
        hmd = ['ok', 'pose', '0', '0', '1.6', '0', '1', '0', '0', '0']
        with patch('backends.sendToSteamVR', return_value=hmd) as send:
            self.assertTrue(SteamVRBackend().updatepose(self.params, self.pose, self.rotations, None))
        self.assertEqual(send.call_count, 4)
        self.assertEqual(send.call_args_list[0].args[0], 'getdevicepose 0')
        for call in send.call_args_list[1:]:
            command = call.args[0].split()
            self.assertEqual(command[0], 'updatepose')
            self.assertTrue(np.isfinite([float(v) for v in command[2:]]).all())

    def test_invalid_hmd_response_does_not_emit_tracker_updates(self):
        for value in ('nan', 'invalid', 'inf'):
            response = ['ok', 'pose', '0', value, '0', '0', '1', '0', '0', '0']
            with patch('backends.sendToSteamVR', return_value=response) as send:
                self.assertFalse(SteamVRBackend().updatepose(self.params, self.pose, self.rotations, None))
                send.assert_called_once_with('getdevicepose 0')


if __name__ == '__main__':
    unittest.main()
