"""Conversão dos keypoints e integração com driver sem inventar punho global."""
import copy
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch
import numpy as np
from scipy.spatial.transform import Rotation as R

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from finger_tracking import HandFrame,FINGERS,FingerTracking
from steamvr_skeleton import skeleton_transforms,prepare_hand,PARENTS
from steamvr_hands_backend import SteamVRHandsBackend
from steamvr_protocol import DriverConnectionError,encode_frame
from pose_validation import InvalidPose
from test_first_improvement import run_one_frame
from test_finger_tracking import detection
from hand_quality import HandQualitySettings
import mediapipepose as app
from inference_gui import InferenceWindow


def hand_points():
    points=np.zeros((21,3))
    points[1:5]=[[-.03,-.02,0],[-.05,-.045,0],[-.065,-.065,0],[-.08,-.08,0]]
    for start,x,y in ((5,-.03,-.06),(9,0,-.07),(13,.025,-.065),(17,.045,-.055)):
        for offset,dy in enumerate((0,.03,.05,.07)):points[start+offset]=[x,y-dy,0]
    return points


def fixture(side='Left'):
    points=hand_points()
    image_points=points.copy();image_points[:,:2]=points[:,:2]*3+[.5,.5]
    frame=HandFrame(side,.95,image_points,dict.fromkeys(FINGERS,.2),dict.fromkeys(FINGERS,.1),points)
    world=[NS(x=0.,y=0.,z=0.,visibility=.95) for _ in range(33)]
    image=[NS(x=.5,y=.5,z=0.,visibility=.95) for _ in range(33)]
    for i,p in ((11,(-.2,-.5,0)),(12,(.2,-.5,0)),(15,(-.3,-.25,.1)),(16,(.3,-.25,.1))):
        world[i].x,world[i].y,world[i].z=p
    params=NS(global_rot_x=R.identity(),global_rot_y=R.identity(),global_rot_z=R.identity(),
        posescale=1.,hmd_to_neck_offset=[0,-.2,.1],min_visibility=.5,backend=4,
        use_hands=False,ignore_hip=False,preview_skeleton=False,additional_smoothing=0.,recalibrate=False)
    return frame,world,image,params


def forward(bones):
    positions=np.zeros((31,3));rotations=[R.identity() for _ in range(31)]
    for index,parent in enumerate(PARENTS[1:],1):
        positions[index]=positions[parent]+rotations[parent].apply(bones[index,:3])
        rotations[index]=rotations[parent]*R.from_quat(bones[index,[4,5,6,3]])
    return positions,rotations


class SkeletalGeometryTests(unittest.TestCase):
    def test_hierarchy_reconstructs_observed_landmarks_for_both_hands(self):
        points=hand_points()
        for side in ('Left','Right'):
            wrist,bones=skeleton_transforms(points,side)
            self.assertEqual(bones.shape,(31,7))
            self.assertTrue(np.isfinite(bones).all())
            np.testing.assert_allclose(np.linalg.norm(bones[:,3:],axis=1),1)
            positions,rotations=forward(bones)
            for bone,keypoint in ((2,1),(3,2),(4,3),(5,4),(7,5),(8,6),(9,7),(10,8),
                                  (12,9),(13,10),(14,11),(15,12),(17,13),(18,14),(19,15),(20,16),(22,17),(23,18),(24,19),(25,20)):
                np.testing.assert_allclose(positions[bone],wrist.T@(points[keypoint]-points[0]),atol=1e-10)
            for bone,keypoint in ((26,4),(27,8),(28,12),(29,16),(30,20)):
                np.testing.assert_allclose(positions[bone],wrist.T@(points[keypoint]-points[0]),atol=1e-10)
            np.testing.assert_allclose(positions[6],wrist.T@((points[0]+points[5])/2-points[0]),atol=1e-10)

    def test_relative_bones_invariant_to_global_rotation_and_translation(self):
        points=hand_points();wrist,bones=skeleton_transforms(points,'Left')
        rotation=R.from_euler('xyz',[20,30,40],degrees=True)
        changed=rotation.apply(points)+[2,3,4]
        new_wrist,new_bones=skeleton_transforms(changed,'Left')
        np.testing.assert_allclose(new_wrist,rotation.as_matrix()@wrist,atol=1e-10)
        np.testing.assert_allclose(new_bones[:,:3],bones[:,:3],atol=1e-10)
        for a,b in zip(new_bones[:,3:],bones[:,3:]):
            self.assertAlmostEqual(abs(np.dot(a,b)),1)

    def test_openvr_bind_direction_points_forward_with_palms_inward(self):
        points=hand_points()
        canonical=np.column_stack((points[:,2],-points[:,0],points[:,1]))
        for side in ('Left','Right'):
            wrist,bones=skeleton_transforms(canonical,side)
            np.testing.assert_allclose(wrist,np.eye(3),atol=1e-10)
            _,rotations=forward(bones)
            longitudinal=rotations[12].apply([1 if side=='Left' else -1,0,0])
            np.testing.assert_allclose(longitudinal,[0,0,-1],atol=1e-10)

    def test_each_finger_can_move_independently(self):
        points=hand_points();_,base=skeleton_transforms(points,'Left')
        points[7,2]=.02;points[8,2]=.04
        _,changed=skeleton_transforms(points,'Left')
        self.assertFalse(np.allclose(base[8:11],changed[8:11]))
        np.testing.assert_allclose(base[11:26],changed[11:26])
        np.testing.assert_allclose(base[2:6],changed[2:6])

    def test_invalid_and_degenerate_geometry(self):
        for points,side in ((np.zeros((21,3)),'Left'),(hand_points()[:20],'Left'),
                            (np.full((21,3),math.nan),'Left'),(hand_points(),'Other')):
            with self.assertRaises(ValueError):skeleton_transforms(points,side)

    def test_pose_anchor_and_wire_validation(self):
        frame,world,image,params=fixture()
        pose,bones=prepare_hand(frame,world,image,(480,640,3),params)
        np.testing.assert_allclose(pose[:3],[.3,-.45,.2])
        self.assertEqual(len(encode_frame(0,1,pose,bones)),916)
        original=frame.world_points.copy()
        prepare_hand(frame,world,image,(480,640,3),params)
        np.testing.assert_array_equal(frame.world_points,original)

    def test_no_fake_wrist_when_pose_absent_hidden_or_hand_mismatch(self):
        frame,world,image,params=fixture()
        for missing in (None,[],4):
            with self.assertRaises(InvalidPose):prepare_hand(frame,missing,image,(480,640,3),params)
        for index in (11,12,15):
            hidden=copy.deepcopy(image);hidden[index].visibility=0
            with self.assertRaises(InvalidPose):prepare_hand(frame,world,hidden,(480,640,3),params)
        image[15].x=0
        with self.assertRaises(InvalidPose):prepare_hand(frame,world,image,(480,640,3),params)

    def test_low_confidence_and_invalid_spatial_data_rejected(self):
        for score in (.1,math.nan,True):
            frame,world,image,params=fixture();frame.score=score
            with self.assertRaises(InvalidPose):prepare_hand(frame,world,image,(480,640,3),params)
        frame,world,image,params=fixture();frame.world_points=None
        with self.assertRaises(InvalidPose):prepare_hand(frame,world,image,(480,640,3),params)
        frame,world,image,params=fixture();world[15].x=math.nan
        with self.assertRaises(InvalidPose):prepare_hand(frame,world,image,(480,640,3),params)

    def test_hands_world_coordinates_unmirror_to_pose_camera_axes(self):
        detector=Mock();detector.process.return_value=detection()
        tracker=FingerTracking(detector,settings=HandQualitySettings(min_palm_pixels=0,confirmation_frames=1))
        frame=tracker.process(np.zeros((120,160,3),np.uint8),mirrored=False)['Left']
        raw=detector.process.return_value.multi_hand_world_landmarks[0].landmark
        self.assertAlmostEqual(frame.world_points[5,0],-raw[5].x)
        frame=tracker.process(np.zeros((120,160,3),np.uint8),mirrored=True)['Left']
        self.assertAlmostEqual(frame.world_points[5,0],raw[5].x)


class HandBackendTests(unittest.TestCase):
    def backend(self):
        backend=SteamVRHandsBackend();backend.hands=Mock();backend.client=Mock()
        return backend

    def test_confirmed_hand_and_missing_other_side(self):
        frame,world,image,params=fixture();backend=self.backend()
        backend.update_hands(params,{'Left':frame},world,image,(480,640,3))
        calls=backend.hands.send.call_args_list
        self.assertEqual(calls[0].args[0],0);self.assertEqual(calls[0].args[1].shape,(7,))
        self.assertEqual(calls[1].args,(1,));self.assertEqual(calls[1].kwargs,{'valid':False})
        self.assertIn('ME:ok',backend.status)

    def test_terminal_reports_actual_rejection_reason_without_changing_invalidation(self):
        frame,_,image,params=fixture();backend=self.backend()
        with patch('builtins.print') as output:
            backend.update_hands(params,{'Left':frame},None,image,(480,640,3))
        self.assertIn('Sem pose/alinhamento',output.call_args.args[0])
        self.assertIn('MD:Mão ausente',output.call_args.args[0])
        self.assertEqual(output.call_args.kwargs,{'flush':True})
        self.assertTrue(all(call.kwargs.get('valid') is False for call in backend.hands.send.call_args_list))

    def test_unchanged_status_not_repeated_even_after_interval(self):
        backend=self.backend()
        with patch('steamvr_hands_backend.time.monotonic',side_effect=[0.,10.,20.]),patch('builtins.print') as output:
            for _ in range(3):backend.report_status()
        output.assert_called_once()

    def test_status_changes_are_limited_and_latest_change_is_eventually_reported(self):
        backend=self.backend()
        with patch('steamvr_hands_backend.time.monotonic',side_effect=[0.,.1,.2,2.]),patch('builtins.print') as output:
            backend.status='SteamVR | ME:Mão ausente';backend.report_status()
            backend.status='SteamVR | ME:ok';backend.report_status()
            backend.status='SteamVR | ME:Sem pose';backend.report_status()
            backend.status='SteamVR | ME:ok';backend.report_status()
        self.assertEqual(output.call_count,2)
        self.assertEqual(output.call_args.args[0],'INFO: SteamVR | ME:ok')

    def test_successful_hand_send_is_preserved_with_terminal_diagnostics(self):
        frame,world,image,params=fixture();backend=self.backend()
        with patch('builtins.print') as output:
            backend.update_hands(params,{'Left':frame},world,image,(480,640,3))
        self.assertIn('ME:ok',output.call_args.args[0])
        self.assertEqual(backend.hands.send.call_count,2)
        self.assertEqual(backend.hands.send.call_args_list[0].args[0],0)
        self.assertFalse(backend.hands.send.call_args_list[0].kwargs.get('valid') is False)

    def test_lost_pose_invalidates_even_when_hand_is_detected(self):
        frame,_,image,params=fixture();backend=self.backend()
        backend.update_hands(params,{'Left':frame},None,image,(480,640,3))
        self.assertTrue(all(call.kwargs.get('valid') is False for call in backend.hands.send.call_args_list))

    def test_reset_is_idempotent_cancels_confirmation_and_clears_histories(self):
        backend=self.backend();backend._invalidated=False;backend.history['hip']=np.ones((2,3))
        backend.request_confirmation(1);backend.reset();backend.reset();backend.tick(10)
        backend.hands.invalidate.assert_called_once();backend.hands.confirm.assert_not_called()
        self.assertEqual(backend.history,{})

    def test_confirmation_waits_three_seconds_and_fires_once(self):
        backend=self.backend();backend.request_confirmation(1)
        backend.tick(3.99);backend.hands.confirm.assert_not_called()
        backend.tick(4);backend.tick(5);backend.hands.confirm.assert_called_once_with()

    def test_driver_error_releases_all_owned_resources(self):
        backend=self.backend();hands=backend.hands;osc=backend.client
        backend._invalidated=False;hands.invalidate.side_effect=OSError('driver exited')
        backend.disconnect();backend.disconnect()
        hands.close.assert_called_once();osc.close.assert_called_once()

    def test_connect_requires_valid_hmd_and_closes_failed_connections(self):
        _,_,_,params=fixture();params.backend_ip='127.0.0.1';params.backend_port=9000
        for valid in (False,True):
            client=Mock();client.status.return_value={'hmd_valid':valid}
            with patch('steamvr_hands_backend.SteamVRHandsClient',return_value=client),patch('backends.udp_client.UDPClient') as osc:
                backend=SteamVRHandsBackend()
                if valid:
                    backend.connect(params);client.invalidate.assert_called_once();backend.disconnect()
                else:
                    with self.assertRaisesRegex(DriverConnectionError,'HMD'):backend.connect(params)
                client.close.assert_called_once();osc.return_value.close.assert_called_once()

    def test_live_loop_routes_body_and_hands_to_combined_backend(self):
        detector=Mock();detector.process.return_value=detection()
        with patch.object(app.mp.solutions.hands,'Hands',return_value=detector):
            backend=run_one_frame(app,True,parameter_overrides={'backend':4,'track_fingers':True,
                'request_fbt_confirmation':True,'hand_quality':HandQualitySettings(min_palm_pixels=0,confirmation_frames=1)})
        backend.updatepose.assert_called_once();backend.update_hands.assert_called_once()
        backend.request_confirmation.assert_called_once();backend.tick.assert_called_once()
        detector.close.assert_called_once()


class HmdCalibrationTests(unittest.TestCase):
    def window(self):
        pose=np.zeros((29,3));pose[0,1]=-1;pose[7,1]=1
        matrix=np.column_stack((np.eye(3),[0,1.7,0]))
        window=Mock()
        window.params=NS(backend=4,pose3d_og=pose,read_hmd_pose=Mock(return_value=matrix),
            calib_tilt=False,calib_rot=False,calib_scale=True,posescale=1.,recalibrate=False)
        return window

    def test_virtual_hmd_reported_height_scales_pose(self):
        window=self.window();InferenceWindow.autocalibrate(window)
        self.assertAlmostEqual(window.params.posescale,.85)
        window.params.read_hmd_pose.assert_called_once();window.set_scale_var.assert_called_once()

    def test_missing_invalid_or_reflected_hmd_cancels(self):
        for matrix in (None,np.zeros((3,4)),np.column_stack((np.diag([-1,1,1]),[0,1.7,0]))):
            window=self.window();window.params.read_hmd_pose.return_value=matrix
            InferenceWindow.autocalibrate(window)
            self.assertEqual(window.params.posescale,1)
            self.assertIn('cancelada',window.params.pose_status)
            window.set_scale_var.assert_not_called()

    def test_zero_hmd_height_never_produces_zero_scale(self):
        window=self.window();window.params.read_hmd_pose.return_value=np.column_stack((np.eye(3),[0,0,0]))
        InferenceWindow.autocalibrate(window)
        self.assertEqual(window.params.posescale,1)
        self.assertIn('Altura HMD',window.params.pose_status)
