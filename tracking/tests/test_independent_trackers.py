import copy
import json
import socket
import tempfile
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import cv2
from pythonosc.osc_packet import OscPacket

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from independent_trackers import (NAMES, prepare_trackers, enabled_names,
                                  tracker_mask, TrackerLifecycle)
from pose_validation import prepare_pose, InvalidPose
from backends import VRChatOSCBackend, SteamVRBackend
from parameters import Parameters
from video_source import VideoFileSource
from test_pose_validation import fixture
from test_first_improvement import run_one_frame
import mediapipepose as app


class PartialValidationTests(unittest.TestCase):
    def test_complete_pose_preserves_original_pipeline(self):
        landmarks, params = fixture()
        original = prepare_pose(landmarks, params)
        current = prepare_trackers(landmarks, params)
        self.assertTrue(all(current.valid.values()))
        np.testing.assert_array_equal(original[0], current.pose)
        np.testing.assert_array_equal(original[1], current.calibration)
        np.testing.assert_array_equal(original[2], current.rotations)

    def test_one_occluded_ankle_keeps_hip_and_other_foot(self):
        for hidden, invalid, valid in ((27, 'left_foot', 'right_foot'), (28, 'right_foot', 'left_foot')):
            landmarks, params = fixture()
            landmarks[hidden].visibility = .1
            frame = prepare_trackers(landmarks, params)
            self.assertTrue(frame.valid['hip'])
            self.assertTrue(frame.valid[valid])
            self.assertFalse(frame.valid[invalid])
            self.assertIn(invalid, frame.reasons)
            self.assertIsNone(frame.calibration)

    def test_both_feet_missing_keeps_hip(self):
        landmarks, params = fixture()
        landmarks[27].visibility = landmarks[28].visibility = 0
        self.assertEqual(prepare_trackers(landmarks, params).valid,
                         {'hip': True, 'right_foot': False, 'left_foot': False})

    def test_nonfinite_unused_points_do_not_contaminate_valid_trackers(self):
        for index, invalid in ((27, 'left_foot'), (28, 'right_foot'), (0, None)):
            landmarks, params = fixture()
            landmarks[index].x = np.nan
            frame = prepare_trackers(landmarks, params)
            self.assertTrue(np.isfinite(frame.pose).all())
            self.assertTrue(frame.valid['hip'])
            if invalid:
                self.assertFalse(frame.valid[invalid])
            else:
                self.assertTrue(all(frame.valid.values()))
            self.assertIsNone(frame.calibration)

    def test_common_anchor_missing_blocks_all_trackers(self):
        for index in (11, 12, 23, 24):
            landmarks, params = fixture()
            landmarks[index].visibility = 0
            self.assertFalse(any(prepare_trackers(landmarks, params).valid.values()))

    def test_degenerate_leg_does_not_block_other_orientations(self):
        landmarks, params = fixture()
        landmarks[26].x = landmarks[28].x
        landmarks[26].y = landmarks[28].y
        landmarks[26].z = landmarks[28].z
        frame = prepare_trackers(landmarks, params)
        self.assertFalse(frame.valid['right_foot'])
        self.assertTrue(frame.valid['left_foot'])
        self.assertTrue(frame.valid['hip'])

    def test_experimental_foot_and_hands_have_their_own_dependencies(self):
        landmarks, params = fixture()
        params.feet_rotation = True
        landmarks[31].visibility = 0
        frame = prepare_trackers(landmarks, params)
        self.assertFalse(frame.valid['left_foot'])
        self.assertTrue(frame.valid['right_foot'])
        landmarks, params = fixture()
        params.use_hands = True
        landmarks[17].visibility = 0
        frame = prepare_trackers(landmarks, params)
        self.assertFalse(frame.valid['left_hand'])
        self.assertTrue(frame.valid['right_hand'])
        self.assertTrue(frame.valid['hip'])

    def test_original_fallback_requires_other_ankle_only_when_used(self):
        landmarks, params = fixture()
        for axis in ('x', 'y', 'z'):
            setattr(landmarks[25], axis, (getattr(landmarks[23], axis) + getattr(landmarks[27], axis)) / 2)
        landmarks[28].visibility = 0
        frame = prepare_trackers(landmarks, params)
        self.assertFalse(frame.valid['left_foot'])
        self.assertTrue(frame.valid['hip'])

    def test_preview_retains_conservative_validation(self):
        landmarks, params = fixture()
        params.preview_skeleton = True
        landmarks[27].visibility = 0
        with self.assertRaises(InvalidPose):
            prepare_trackers(landmarks, params)

    def test_invalid_inputs_and_threshold(self):
        landmarks, params = fixture()
        for invalid in (None, [], landmarks[:-1], 4):
            with self.assertRaises(InvalidPose):
                prepare_trackers(invalid, params)
        params.min_visibility = np.nan
        with self.assertRaises(InvalidPose):
            prepare_trackers(landmarks, params)

    def test_masks_and_disabled_features(self):
        _, params = fixture()
        params.ignore_hip = True
        params.use_hands = True
        params.backend = 2
        self.assertEqual(enabled_names(params), ('right_foot', 'left_foot'))
        for invalid in ([], {'unknown': True}, {'right_foot': 'yes'}):
            with self.assertRaises(ValueError):
                tracker_mask(params, invalid)
        self.assertEqual(tracker_mask(params, {'hip': True}), {'right_foot': False, 'left_foot': False})

    def test_camera_loop_emits_partial_mask_and_keeps_calibration_invalid(self):
        original = app.prepare_trackers
        def hide_left(landmarks, params, **options):
            landmarks[27].visibility = 0
            return original(landmarks, params, **options)
        with patch.object(app, 'prepare_trackers', side_effect=hide_left):
            backend = run_one_frame(app, True, existing_calibration=True)
        self.assertEqual(backend.updatepose.call_args.kwargs['valid_trackers'],
                         {'hip': True, 'right_foot': True, 'left_foot': False})
        self.assertFalse(hasattr(backend.test_params, 'pose3d_og'))


class LifecycleTests(unittest.TestCase):
    def test_default_expires_only_missing_tracker_immediately(self):
        life = TrackerLifecycle(NAMES[:3])
        self.assertEqual(life.update(dict.fromkeys(NAMES[:3], True), 0), set())
        self.assertEqual(life.update({'hip': True, 'right_foot': True}, .04), {'left_foot'})
        self.assertEqual(life.states, {'hip': 'active', 'right_foot': 'active', 'left_foot': 'expired'})
        self.assertEqual(life.update({'hip': True, 'right_foot': True}, .08), set())
        self.assertEqual(life.update(dict.fromkeys(NAMES[:3], True), .12), set())
        self.assertEqual(life.states['left_foot'], 'active')

    def test_positive_timeout_boundary_and_recovery(self):
        life = TrackerLifecycle(('hip', 'left_foot'))
        life.update({'hip': True, 'left_foot': True}, 0, .5)
        self.assertEqual(life.update({'hip': True}, .25, .5), set())
        self.assertEqual(life.states['left_foot'], 'missing')
        self.assertEqual(life.update({'hip': True}, .5, .5), {'left_foot'})
        self.assertEqual(life.update({'hip': True, 'left_foot': True}, .6, .5), set())
        self.assertTrue(all(state == 'active' for state in life.states.values()))

    def test_gap_before_new_valid_sample_expires_old_cache(self):
        life = TrackerLifecycle(('hip',))
        life.update({'hip': True}, 0, .2)
        self.assertEqual(life.update({'hip': True}, .5, .2), {'hip'})
        self.assertEqual(life.states['hip'], 'active')

    def test_decimal_timeout_boundary_does_not_wait_an_extra_frame(self):
        life = TrackerLifecycle(('hip',))
        life.update({'hip': True}, .1, .2)
        self.assertEqual(life.update({'hip': False}, .3, .2), {'hip'})

    def test_zero_timeout_does_not_reset_consecutive_valid_smoothing(self):
        life = TrackerLifecycle(('hip',))
        life.update({'hip': True}, 0)
        self.assertEqual(life.update({'hip': True}, 1), set())

    def test_invalid_times_masks_and_regressions_do_not_mutate_state(self):
        life = TrackerLifecycle(('hip',))
        life.update({'hip': True}, 1)
        for timestamp, timeout in ((np.nan, 0), (np.inf, 0), (2, -1), (2, np.nan), (0, 0), (-1, 0), (None, 0)):
            with self.assertRaises(ValueError):
                life.update({'hip': False}, timestamp, timeout)
        for invalid in (None, {'left_foot': True}, {'hip': 'true'}):
            with self.assertRaises(ValueError):
                life.update(invalid, 2)
        self.assertEqual(life.last_seen['hip'], 1)
        self.assertEqual(life.states['hip'], 'active')

    def test_invalidate_and_restart_clear_local_state(self):
        life = TrackerLifecycle(('hip',))
        life.update({'hip': True}, 5)
        self.assertEqual(life.invalidate(), {'hip'})
        self.assertEqual(life.states['hip'], 'expired')
        life.reset()
        self.assertEqual(life.states['hip'], 'unavailable')
        life.update({'hip': True}, 0)

    def test_timeout_parameter_validation(self):
        params = Parameters.__new__(Parameters)
        params.tracker_timeout = 0
        self.assertTrue(params.set_tracker_timeout('.2'))
        for invalid in (-1, np.nan, np.inf, 'bad', None):
            self.assertFalse(params.set_tracker_timeout(invalid))
            self.assertEqual(params.tracker_timeout, .2)
        self.assertTrue(params.set_tracker_timeout(0))
        with self.assertRaises(ValueError):
            TrackerLifecycle(('invalid',))


class IndependentBackendTests(unittest.TestCase):
    def setUp(self):
        landmarks, self.params = fixture()
        self.params.additional_smoothing = .7
        self.params.hmd_to_neck_offset = [0, -.2, .1]
        self.params.recalibrate = False
        self.params.posescale = 1.2
        self.params.ignore_hip = False
        self.params.camera_latency = 0
        self.frame = prepare_trackers(landmarks, self.params)
        self.backend = VRChatOSCBackend()
        self.backend.client = Mock()

    def update(self, frame=None, mask=None):
        frame = frame or self.frame
        return self.backend.updatepose(self.params, frame.pose, frame.rotations, frame.hands,
                                       valid_trackers=frame.valid if mask is None else mask)

    def packet(self):
        return {item.message.address: item.message.params for item in
                OscPacket(self.backend.client.send.call_args.args[0].dgram).messages}

    def test_partial_osc_has_only_valid_trackers_and_no_ghost_positions(self):
        self.assertTrue(self.update(mask={'hip': True, 'right_foot': True}))
        addresses = set(self.packet())
        self.assertEqual(addresses, {'/tracking/trackers/head/position',
            '/tracking/trackers/1/position', '/tracking/trackers/1/rotation',
            '/tracking/trackers/2/position', '/tracking/trackers/2/rotation'})
        self.assertNotIn('left_foot', self.backend.history)

    def test_fully_valid_wire_payloads_match_frozen_original(self):
        root = Path(__file__).parent / 'fixtures'
        data = json.loads((root / 'rotations_reference.json').read_text())
        expected = json.loads((root / 'osc_reference.json').read_text())
        pose = np.array(data['pose'])
        for index, positions in enumerate((pose, pose * 1.5 + np.array([.1, -.2, .3]))):
            self.backend.updatepose(self.params, positions, data['legs'], None)
            actual = self.packet()
            self.assertEqual(set(actual), set(expected[index]))
            for address in actual:
                np.testing.assert_allclose(actual[address], expected[index][address], rtol=1e-7, atol=1e-6)

    def test_expiration_clears_only_lost_history_and_recovery_starts_fresh(self):
        self.update()
        right_before = self.backend.history['right_foot'].copy()
        self.backend.expire_trackers({'left_foot'})
        self.assertNotIn('left_foot', self.backend.history)
        np.testing.assert_array_equal(self.backend.history['right_foot'], right_before)
        shifted = copy.deepcopy(self.frame)
        shifted.pose[5] += 1
        self.update(shifted)
        np.testing.assert_array_equal(self.backend.history['left_foot'], shifted.pose[[5, 7]])

    def test_missing_tracker_is_not_resent_even_when_its_history_is_retained(self):
        self.update()
        old = self.backend.history['left_foot'].copy()
        self.update(mask={'hip': True, 'right_foot': True})
        self.assertNotIn('/tracking/trackers/3/position', self.packet())
        np.testing.assert_array_equal(old, self.backend.history['left_foot'])

    def test_all_lost_does_not_send_head_only_bundle(self):
        self.assertTrue(self.update(mask={}))
        self.backend.client.send.assert_not_called()
        self.assertEqual(self.backend.history, {})

    def test_failed_transport_does_not_commit_history(self):
        self.backend.client.send.side_effect = OSError('transport unavailable')
        with self.assertRaises(OSError):
            self.update()
        self.assertEqual(self.backend.history, {})

    def test_values_outside_osc_float_range_are_rejected_without_sending(self):
        huge = copy.deepcopy(self.frame)
        huge.pose[0] = np.finfo(np.float32).max * 2
        self.assertFalse(self.update(huge))
        self.backend.client.send.assert_not_called()
        self.assertEqual(self.backend.history, {})

    def test_stream_reset_clears_all_histories(self):
        self.update()
        self.backend.reset()
        self.assertEqual(self.backend.history, {})

    def test_steamvr_sends_selected_device_ids_and_keeps_other_roles(self):
        hmd = ['ok', 'pose', '0', '0', '1.6', '0', '1', '0', '0', '0']
        with patch('backends.sendToSteamVR', return_value=hmd) as send:
            SteamVRBackend().updatepose(self.params, self.frame.pose, self.frame.rotations, None,
                                       valid_trackers={'hip': True, 'right_foot': True})
        self.assertEqual([call.args[0].split()[:2] for call in send.call_args_list[1:]],
                         [['updatepose', '0'], ['updatepose', '1']])
        self.params.ignore_hip = True
        with patch('backends.sendToSteamVR', return_value=hmd) as send:
            SteamVRBackend().updatepose(self.params, self.frame.pose, self.frame.rotations, None)
        self.assertEqual([call.args[0].split()[:2] for call in send.call_args_list[1:]],
                         [['updatepose', '0'], ['updatepose', '1']])

    def test_invalid_mask_or_missing_hand_quaternion_is_rejected(self):
        self.assertFalse(self.update(mask={'hip': 'yes'}))
        self.params.use_hands = True
        with patch('backends.sendToSteamVR') as send:
            self.assertFalse(SteamVRBackend().updatepose(self.params, self.frame.pose, self.frame.rotations, None))
            send.assert_not_called()

    def test_steamvr_preview_stays_complete_and_rejects_partial_masks(self):
        self.params.preview_skeleton = True
        hmd = ['ok', 'pose', '0', '0', '1.6', '0', '1', '0', '0', '0']
        with patch('backends.sendToSteamVR', return_value=hmd) as send:
            self.assertFalse(SteamVRBackend().updatepose(self.params, self.frame.pose, self.frame.rotations,
                                                       None, valid_trackers={'hip': True}))
            send.assert_not_called()
            self.assertTrue(SteamVRBackend().updatepose(self.params, self.frame.pose, self.frame.rotations, None))
        self.assertEqual(send.call_count, 24)  # HMD + os mesmos 23 pontos do preview.

    def test_steamvr_missing_hand_does_not_block_body_or_other_hand(self):
        landmarks, _ = fixture()
        self.params.use_hands = True
        landmarks[17].visibility = 0
        frame = prepare_trackers(landmarks, self.params)
        hmd = ['ok', 'pose', '0', '0', '1.6', '0', '1', '0', '0', '0']
        with patch('backends.sendToSteamVR', return_value=hmd) as send:
            self.assertTrue(SteamVRBackend().updatepose(self.params, frame.pose, frame.rotations,
                                                       frame.hands, valid_trackers=frame.valid))
        self.assertEqual([call.args[0].split()[1] for call in send.call_args_list[1:]], ['0', '1', '2', '4'])
        self.params.ignore_hip = True
        with patch('backends.sendToSteamVR', return_value=hmd) as send:
            self.assertTrue(SteamVRBackend().updatepose(self.params, frame.pose, frame.rotations,
                                                       frame.hands, valid_trackers=frame.valid))
        self.assertEqual([call.args[0].split()[1] for call in send.call_args_list[1:]], ['0', '1', '3'])

    def test_real_udp_transport_omits_occluded_tracker(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, \
             socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            receiver.bind(('127.0.0.1', 0))
            receiver.settimeout(2)
            self.backend.client.send.side_effect = lambda bundle: sender.sendto(bundle.dgram, receiver.getsockname())
            self.update(mask={'hip': True, 'right_foot': True})
            packet = OscPacket(receiver.recv(4096))
        addresses = {item.message.address for item in packet.messages}
        self.assertIn('/tracking/trackers/1/position', addresses)
        self.assertIn('/tracking/trackers/2/position', addresses)
        self.assertNotIn('/tracking/trackers/3/position', addresses)


class RecordedOcclusionIntegrationTests(unittest.TestCase):
    def test_real_video_pipeline_loss_recovery_and_end_clear_histories(self):
        landmarks, params = fixture()
        params.__dict__.update(webui=False, backend=2, exit_ready=False, model=1,
            min_tracking_confidence=.5, smooth_landmarks=True, static_image=False,
            smoothing=0., additional_smoothing=.7, rotate_image=None, mirror=False,
            maximgsize=640, paused=False, log_frametime=False, input_mode='video',
            restart_input=False, cancel_input=False, input_status='', tracker_timeout=0.,
            posescale=1.2, hmd_to_neck_offset=[0, -.2, .1], recalibrate=False)
        missing = copy.deepcopy(landmarks)
        missing[27].visibility = 0
        recovered = copy.deepcopy(landmarks)
        recovered[27].x += .1
        results = [SimpleNamespace(pose_world_landmarks=SimpleNamespace(landmark=points),
                   pose_landmarks=SimpleNamespace(landmark=[SimpleNamespace(x=.5,y=.5,z=0,visibility=p.visibility) for p in points]))
                   for points in (landmarks, missing, recovered)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'occlusion.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 25., (160, 120))
            self.assertTrue(writer.isOpened())
            try:
                for _ in results:
                    writer.write(np.zeros((120, 160, 3), np.uint8))
            finally:
                writer.release()
            now = [0.]
            source = VideoFileSource(path, clock=lambda: now[0])
            params.video_path = str(path)
            self.addCleanup(source.close)
            backend = VRChatOSCBackend()
            backend.client = Mock()
            detector = Mock()
            detector.process.side_effect = results
            states = []
            def display(*args):
                states.append(params.tracker_status)
            def key(_):
                now[0] += 1
                if now[0] > 10:
                    raise AssertionError('Video nao terminou')
                return 27 if source.state == 'completed' else -1
            with ExitStack() as stack:
                for target, kwargs in (
                    ('parameters.Parameters', {'return_value': params}),
                    ('VRChatOSCBackend', {'return_value': backend}),
                    ('VideoFileSource', {'return_value': source}),
                    ('threading.Thread', {}),
                    ('inference_gui.create_inference_gui', {'return_value': Mock()}),
                    ('mp.solutions.pose.Pose', {'return_value': detector}),
                    ('cv2.namedWindow', {}), ('cv2.imshow', {'side_effect': display}),
                    ('cv2.destroyAllWindows', {}), ('cv2.waitKey', {'side_effect': key}),
                    ('shutdown', {'side_effect': SystemExit}),
                ):
                    stack.enter_context(patch.object(app, target, **kwargs) if '.' not in target
                        else patch('mediapipepose.' + target, **kwargs))
                stack.enter_context(patch.object(backend, 'connect'))
                with self.assertRaises(SystemExit):
                    app.main()
            self.assertEqual(detector.process.call_count, 3)
            self.assertEqual(backend.client.send.call_count, 3)
            packets = [{entry.message.address: entry.message.params for entry in OscPacket(call.args[0].dgram).messages}
                       for call in backend.client.send.call_args_list]
            self.assertNotIn('/tracking/trackers/3/position', packets[1])
            self.assertIn('/tracking/trackers/1/position', packets[1])
            self.assertIn('/tracking/trackers/2/position', packets[1])
            raw = prepare_trackers(recovered, params).pose * params.posescale
            expected = raw[5] - (raw[7] - params.hmd_to_neck_offset)
            expected[2] *= -1
            np.testing.assert_allclose(packets[2]['/tracking/trackers/3/position'], expected, rtol=1e-7, atol=1e-6)
            self.assertIn('PE:expirado', states[1])
            self.assertIn('Q:ok', states[1])
            self.assertIn('PD:ok', states[1])
            self.assertEqual(backend.history, {})
            self.assertIsNone(source.cap)
            detector.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
