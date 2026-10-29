"""OSC corporal/avatares: geometria, configurações, regressões e UDP real."""
import copy
import json
import math
from pathlib import Path
import socket
import sys
import tempfile
from contextlib import ExitStack
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import numpy as np
from scipy.spatial.transform import Rotation
from pythonosc.osc_packet import OscPacket
from pythonosc.udp_client import UDPClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from osc_body import EXTRA_IDS, prepare_extra_trackers
from osc_hands import default_profile, validate_profile, load_profile, OSCProfileError
from finger_tracking import FingerTracking, HandFrame, FINGERS, finger_spreads
from backends import VRChatOSCBackend
from independent_trackers import prepare_trackers
from test_finger_tracking import detection
from test_first_improvement import run_one_frame
from hand_quality import HandQualitySettings
import mediapipepose as app
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from monitor_osc_tracking import monitor
import validate_osc_models as model_check


def body():
    points = [NS(x=0., y=0., z=0., visibility=.95) for _ in range(33)]
    for i, xyz in {11:(-.2,-.5,0),12:(.2,-.5,0),23:(-.15,0,0),24:(.15,0,0),
                   13:(-.25,-.25,0),14:(.25,-.25,0),15:(-.3,0,.1),16:(.3,0,.1),
                   25:(-.15,.4,.05),26:(.15,.4,.05),27:(-.15,.8,0),28:(.15,.8,0)}.items():
        points[i].x, points[i].y, points[i].z = xyz
    image = [NS(x=.5, y=.5, z=0., visibility=.95) for _ in range(33)]
    params = NS(global_rot_z=Rotation.identity(), global_rot_x=Rotation.identity(),
                global_rot_y=Rotation.identity(), posescale=1., hmd_to_neck_offset=[0,-.2,.1],
                min_visibility=.5, feet_rotation=False, use_hands=False, ignore_hip=False,
                backend=2, additional_smoothing=0., recalibrate=False, preview_skeleton=False)
    return points, image, params


def values(bundle):
    return {m.message.address: m.message.params for m in OscPacket(bundle.dgram).messages}


class ExtendedBodyTests(unittest.TestCase):
    def test_five_additional_ids_and_anatomical_positions(self):
        world, image, params = body()
        extras = prepare_extra_trackers(world, image, params)
        self.assertEqual(set(extras), set(EXTRA_IDS))
        np.testing.assert_allclose(extras['left_elbow'][0][0], [.25,.25,0])
        np.testing.assert_allclose(extras['chest'][0][0], [0,.375,0])
        for pair, quaternion in extras.values():
            self.assertEqual(pair.shape, (2,3))
            self.assertAlmostEqual(np.linalg.norm(quaternion), 1.)

    def test_missing_elbow_only_removes_its_tracker(self):
        world, image, params = body()
        image[13].visibility = 0
        extras = prepare_extra_trackers(world, image, params)
        self.assertEqual(set(extras), set(EXTRA_IDS) - {'left_elbow'})

    def test_upper_body_does_not_invent_hips_or_knees(self):
        world, image, params = body()
        for i in range(23,33):
            image[i].visibility = 0
        self.assertEqual(set(prepare_extra_trackers(world,image,params)), {'left_elbow','right_elbow'})
        image[11].visibility = 0
        self.assertEqual(prepare_extra_trackers(world,image,params), {})

    def test_world_confidence_nonfinite_and_offscreen_reject_independently(self):
        for attribute, value, image_side in (('visibility',0,False),('x',math.nan,False),('x',1e308,False),('x',1.5,True)):
            world, image, params = body()
            setattr((image if image_side else world)[26],attribute,value)
            result = prepare_extra_trackers(world,image,params)
            self.assertNotIn('right_knee', result)
            self.assertIn('left_knee', result)

    def test_degenerate_axes_not_sent(self):
        world, image, params = body()
        world[13] = copy.copy(world[11])
        self.assertNotIn('left_elbow', prepare_extra_trackers(world,image,params))
        world[11] = copy.copy(world[12])
        self.assertEqual(prepare_extra_trackers(world,image,params), {})

    def test_transform_matches_original_order_and_preserves_inputs(self):
        world, image, params = body()
        original = copy.deepcopy(world)
        baseline = prepare_extra_trackers(world,image,params)
        params.global_rot_z = Rotation.from_euler('z',10,degrees=True)
        params.global_rot_x = Rotation.from_euler('x',20,degrees=True)
        params.global_rot_y = Rotation.from_euler('y',30,degrees=True)
        rotated = prepare_extra_trackers(world,image,params)
        for name, (pair, _) in baseline.items():
            for r in (params.global_rot_z,params.global_rot_x,params.global_rot_y):
                pair = r.apply(pair)
            np.testing.assert_allclose(rotated[name][0],pair)
        self.assertEqual(world,original)

    def test_no_world_and_invalid_alignment(self):
        world, image, params = body()
        for missing in (None, [], world[:32], 4):
            self.assertEqual(prepare_extra_trackers(missing,image,params),{})
        params.posescale = math.nan
        self.assertEqual(prepare_extra_trackers(world,image,params),{})

    def test_real_udp_eight_trackers_float_positions_rotations(self):
        world,image,params = body()
        frame = prepare_trackers(world,params,image_landmarks=image)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0)); receiver.settimeout(2)
            backend = VRChatOSCBackend(); backend.client = UDPClient(*receiver.getsockname())
            self.assertTrue(backend.updatepose(params,frame.pose,frame.rotations,frame.hands,
                frame.valid,prepare_extra_trackers(world,image,params)))
            packet = OscPacket(receiver.recv(65535))
            backend.disconnect()
        messages = {m.message.address:m.message.params for m in packet.messages}
        self.assertEqual(len(messages),17)  # Cabeça de referência + 8 pares.
        for tracker_id in range(1,9):
            for kind in ('position','rotation'):
                vector = messages[f'/tracking/trackers/{tracker_id}/{kind}']
                self.assertEqual(len(vector),3)
                self.assertTrue(all(type(v) is float and math.isfinite(v) for v in vector))
        np.testing.assert_allclose(messages['/tracking/trackers/7/position'],[.25,-.45,-.1],atol=1e-7)

    def test_partial_elbows_send_even_without_legacy_trackers(self):
        world,image,params = body()
        for i in range(23,33):image[i].visibility=0
        frame = prepare_trackers(world,params,image_landmarks=image)
        self.assertFalse(any(frame.valid.values()))
        backend = VRChatOSCBackend();backend.client=Mock()
        backend.updatepose(params,frame.pose,frame.rotations,frame.hands,frame.valid,
                           prepare_extra_trackers(world,image,params))
        self.assertEqual(set(values(backend.client.send.call_args.args[0])),
                         {'/tracking/trackers/head/position'} | {f'/tracking/trackers/{i}/{kind}' for i in (7,8) for kind in ('position','rotation')})

    def test_loss_clears_smoothing_and_recovers_without_old_sample(self):
        world,image,params = body()
        frame = prepare_trackers(world,params,image_landmarks=image)
        backend = VRChatOSCBackend(); backend.client=Mock()
        extras=prepare_extra_trackers(world,image,params)
        backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,extras)
        self.assertIn('left_elbow',backend.history)
        backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,{})
        self.assertNotIn('left_elbow',backend.history)
        params.additional_smoothing=.9
        extras['left_elbow'][0][0,0] += 1
        backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,extras)
        np.testing.assert_allclose(backend.history['left_elbow'],extras['left_elbow'][0])
        backend.reset();self.assertEqual(backend.history,{})

    def test_invalid_extras_block_packet_atomically(self):
        world,image,params=body(); frame=prepare_trackers(world,params,image_landmarks=image)
        for extra in ({'unknown':None}, {'chest':(np.zeros((2,3)),[0,0,0,0])},
                      {'chest':(np.full((2,3),math.inf),[0,0,0,1])}, {'chest':None}, []):
            backend=VRChatOSCBackend();backend.client=Mock()
            self.assertFalse(backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,extra))
            backend.client.send.assert_not_called()

    def test_main_passes_extras_and_disabled_keeps_old_call(self):
        backend=run_one_frame(app,True,parameter_overrides={'osc_full_body':True,
            'posescale':1.,'hmd_to_neck_offset':[0,-.2,.1]})
        self.assertIn('extra_trackers',backend.updatepose.call_args.kwargs)
        backend=run_one_frame(app,True,parameter_overrides={'osc_full_body':False})
        self.assertNotIn('extra_trackers',backend.updatepose.call_args.kwargs)

    def test_disconnect_is_idempotent_and_clears_history(self):
        backend=VRChatOSCBackend(); client=Mock(); backend.client=client
        backend.history['chest']=np.ones((2,3))
        backend.disconnect();backend.disconnect()
        client.close.assert_called_once()
        self.assertIsNone(backend.client)
        self.assertEqual(backend.history,{})

    def test_network_failure_does_not_commit_extra_history(self):
        world,image,params=body();frame=prepare_trackers(world,params,image_landmarks=image)
        backend=VRChatOSCBackend();backend.client=Mock();backend.client.send.side_effect=OSError('UDP indisponível')
        with self.assertRaises(OSError):
            backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,prepare_extra_trackers(world,image,params))
        self.assertEqual(backend.history,{})

    def test_recalibration_does_not_send_extra_trackers(self):
        world,image,params=body();frame=prepare_trackers(world,params,image_landmarks=image)
        params.recalibrate=True
        backend=VRChatOSCBackend();backend.client=Mock()
        self.assertTrue(backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,prepare_extra_trackers(world,image,params)))
        backend.client.send.assert_not_called()

    def test_camera_pause_suspends_hands_clears_history_then_resumes(self):
        _,_,params=body()
        params.__dict__.update(webui=False,exit_ready=False,model=1,min_tracking_confidence=.5,
            smooth_landmarks=True,static_image=False,smoothing=0.,rotate_image=None,
            mirror=False,maximgsize=640,paused=True,track_fingers=True,osc_full_body=True,
            log_frametime=False)
        backend=VRChatOSCBackend();client=Mock();backend.client=client
        backend.history['left_elbow']=np.ones((2,3))
        detector=Mock();detector.process.return_value=NS(pose_landmarks=None,pose_world_landmarks=None)
        hands=Mock();hands.process.return_value={};hands.status='Sem mãos'
        image=np.zeros((120,160,3),np.uint8)
        camera=Mock();camera.read_latest.side_effect=lambda:(image.copy(),.01,app.time.perf_counter())
        root=Mock()
        def update():
            if root.update.call_count == 2:
                self.assertEqual(backend.history,{})
                params.paused=False
        root.update.side_effect=update
        with ExitStack() as stack:
            for target,kwargs in (
                ('parameters.Parameters',{'return_value':params}),('VRChatOSCBackend',{'return_value':backend}),
                ('CameraStream',{'return_value':camera}),('inference_gui.create_inference_gui',{'return_value':root}),
                ('mp.solutions.pose.Pose',{'return_value':detector}),('mp.solutions.hands.Hands',{}),
                ('FingerTracking',{'return_value':hands}),('cv2.namedWindow',{}),('cv2.imshow',{}),
                ('cv2.waitKey',{'side_effect':[-1,27]}),('cv2.destroyAllWindows',{}),
                ('shutdown',{'side_effect':SystemExit})):
                stack.enter_context(patch('mediapipepose.'+target,**kwargs))
            stack.enter_context(patch.object(backend,'connect'))
            with self.assertRaises(SystemExit):app.main()
        hands.suspend.assert_called_once();hands.process.assert_called_once();hands.close.assert_called_once()
        detector.process.assert_called_once();camera.close.assert_called_once();client.close.assert_called_once()


class HandProfileTests(unittest.TestCase):
    def hand(self):
        return HandFrame('Left',.95,None,dict.fromkeys(FINGERS,.25),dict.fromkeys(FINGERS,.5))

    def test_default_twenty_channels_and_flags(self):
        profile=load_profile()
        self.assertEqual(len(profile['channels']),20)
        client=Mock();tracker=FingerTracking(None,client,profile=profile)
        tracker.publish({'Left':self.hand()})
        sent=values(client.send.call_args.args[0])
        self.assertEqual(len(sent),12)
        self.assertEqual(sent['/avatar/parameters/MP_Left_Index'],[.25])
        self.assertEqual(sent['/avatar/parameters/MP_Left_Index_Spread'],[.5])
        self.assertEqual(sent['/avatar/parameters/MP_Right_Tracked'],[False])

    def test_custom_addresses_scaling_clamping_enable_and_loss(self):
        profile={'channels':[dict(side='Left',finger='Index',source='curl',
            address='/avatar/parameters/leftIndex',scale=-2,offset=1,min=0,max=1)],
            'tracked':{'Left':'/avatar/parameters/leftTracked'},'enabled':'/avatar/parameters/leapmotion'}
        client=Mock();tracker=FingerTracking(None,client,profile=profile)
        hand=self.hand()
        for curl,expected in ((0,1),(.25,.5),(1,0)):
            hand.curls['Index']=curl;tracker.publish({'Left':hand})
            sent=values(client.send.call_args.args[0])
            self.assertEqual(sent['/avatar/parameters/leftIndex'],[expected])
            self.assertEqual(sent['/avatar/parameters/leapmotion'],[True])
        tracker.suspend()
        self.assertEqual(values(client.send.call_args.args[0]),
            {'/avatar/parameters/leftTracked':[False],'/avatar/parameters/leapmotion':[False]})

    def test_invalid_profile_matrix(self):
        channel=default_profile()['channels'][0]
        invalid=[None,[],{}, {'channels':[]}, {'channels':[channel]*2},
                 {'channels':[channel],'tracked':{'Other':'/avatar/parameters/test'}},
                 {'channels':[channel],'enabled':channel['address']}]
        for key,value in (('side','Other'),('finger','Pinky'),('source','position'),
                          ('scale',math.nan),('scale',10**1000),('offset',True),('min',2),('max',0),
                          ('address','/input/Jump'),('address','/avatar/parameters/a*'),
                          ('address','/avatar/parameters/a\x00b'),('address','/avatar/parameters/a/b')):
            invalid.append({'channels':[dict(channel,**{key:value})]})
        for profile in invalid:
            with self.subTest(profile=profile),self.assertRaises(ValueError):validate_profile(profile)

    def test_json_files_invalid_encoding_corruption_missing_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'perfil.json'
            with self.assertRaises(OSCProfileError):load_profile(path)
            for content in (b'not json',b'\xff',b'x'*131073):
                path.write_bytes(content)
                with self.assertRaises(OSCProfileError):load_profile(path)
            path.write_text(json.dumps(default_profile()),encoding='utf-8')
            self.assertEqual(load_profile(path),load_profile())

    def test_shipped_example_is_complete_and_valid(self):
        example=Path(__file__).resolve().parents[1]/'config'/'osc-hands-example.json'
        self.assertEqual(load_profile(example),load_profile())

    def test_bad_spread_is_omitted_not_published_as_nan(self):
        client=Mock();tracker=FingerTracking(None,client);hand=self.hand()
        for bad in (math.nan,math.inf,True,-.1,1.1,'invalid'):
            hand.spreads['Index']=bad
            tracker.publish({'Left':hand})
            self.assertNotIn('/avatar/parameters/MP_Left_Index_Spread',values(client.send.call_args.args[0]))

    def test_real_udp_body_and_hands_share_destination(self):
        world,image,params=body();frame=prepare_trackers(world,params,image_landmarks=image)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(2)
            client=UDPClient(*receiver.getsockname())
            backend=VRChatOSCBackend();backend.client=client
            backend.updatepose(params,frame.pose,frame.rotations,None,frame.valid,prepare_extra_trackers(world,image,params))
            fingers=FingerTracking(None,client);fingers.publish({'Left':self.hand()})
            packets=[OscPacket(receiver.recv(65535)) for _ in range(2)]
            backend.disconnect()
        addresses=[m.message.address for packet in packets for m in packet.messages]
        self.assertIn('/tracking/trackers/8/position',addresses)
        self.assertIn('/avatar/parameters/MP_Left_Index_Spread',addresses)

    def test_detector_supplies_spreads_and_config_error_releases_resources(self):
        detector=Mock();detector.process.return_value=detection()
        tracker=FingerTracking(detector,settings=HandQualitySettings(min_palm_pixels=0,confirmation_frames=1))
        frames=tracker.process(np.zeros((80,120,3),np.uint8))
        self.assertIsInstance(frames['Left'].spreads,dict)
        with patch.object(app.messagebox,'showerror') as error,patch.object(app,'CameraStream') as camera:
            backend=run_one_frame_without_detector({'track_fingers':True,'osc_hand_profile':'does-not-exist.json'})
        error.assert_called_once();camera.assert_not_called();backend.disconnect.assert_called_once()


def run_one_frame_without_detector(overrides):
    """Configuração inválida é rejeitada ANTES de construir câmera/modelos/Tk."""
    params=NS(webui=False,backend=2,**overrides)
    backend=Mock()
    with patch.object(app.parameters,'Parameters',return_value=params),patch.object(app,'VRChatOSCBackend',return_value=backend),patch.object(app.cv2,'destroyAllWindows'):
        app.main()
    return backend


class SpreadTests(unittest.TestCase):
    def points(self):
        p=np.zeros((21,3))
        for base,x in ((1,-.7),(5,-.4),(9,0),(13,.3),(17,.6)):
            direction=np.array([x,1,0.])
            for step in range(4):p[base+step]=direction*(1+step*.3)
        return [NS(x=x,y=y,z=z) for x,y,z in p]

    def test_neutral_and_forty_five_degrees(self):
        p=self.points()
        for value in finger_spreads(p).values():self.assertAlmostEqual(value,0,places=6)
        p[10]=NS(x=.3,y=1.3,z=0)
        self.assertAlmostEqual(finger_spreads(p)['Middle'],1)

    def test_rotation_translation_scale_invariant_and_no_mutation(self):
        p=self.points();baseline=finger_spreads(p);original=copy.deepcopy(p)
        rotated=Rotation.from_euler('xyz',[25,30,40],degrees=True).apply([[v.x,v.y,v.z] for v in p])*3+2
        result=finger_spreads([NS(x=x,y=y,z=z) for x,y,z in rotated])
        for name,value in baseline.items():self.assertAlmostEqual(result[name],value,places=6)
        self.assertEqual(p,original)

    def test_degenerate_palm_and_invalid_points(self):
        self.assertEqual(finger_spreads([NS(x=0,y=0,z=0)]*21),{})
        for p in (self.points()[:20],[NS(x=math.nan,y=0,z=0)]*21):
            with self.assertRaises(ValueError):finger_spreads(p)


class OSCMonitorTests(unittest.TestCase):
    def test_real_packets_and_malformed_input(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
            receiver.bind(('127.0.0.1',0))
            sender.sendto(b'invalid OSC',receiver.getsockname())
            client=UDPClient(*receiver.getsockname())
            try:
                FingerTracking(None,client).publish({})
                result=monitor(receiver,seconds=1,packets=2)
            finally:
                client.close()
        self.assertEqual(result['packets'],2)
        self.assertEqual(result['malformed'],1)
        self.assertEqual(result['last_values']['/avatar/parameters/MP_Left_Tracked'],[False])

    def test_timeout_without_data(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0))
            result=monitor(receiver,seconds=.01)
        self.assertEqual(result['packets'],0)
        self.assertEqual(result['addresses'],{})

    def test_invalid_limits(self):
        for seconds,packets in ((0,0),(61,0),(math.nan,0),(math.inf,0),(1,-1),(1,.5)):
            with self.assertRaises(ValueError):monitor(Mock(),seconds,packets)


class ModelCheckTests(unittest.TestCase):
    def test_real_image_read_converts_rgb_and_rejects_corrupt_file(self):
        import cv2
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'image.png'
            bgr=np.zeros((16,16,3),np.uint8);bgr[:,:,2]=255
            self.assertTrue(cv2.imwrite(str(path),bgr))
            np.testing.assert_array_equal(model_check.read_rgb(path)[0,0],[255,0,0])
            path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):model_check.read_rgb(path)

    def test_no_pose_releases_backend_and_detector(self):
        from unittest.mock import MagicMock
        pose=MagicMock();pose.__enter__.return_value.process.return_value=NS(pose_world_landmarks=None)
        backend=Mock()
        with patch.object(model_check,'read_rgb',return_value=np.zeros((80,120,3),np.uint8)), \
             patch.object(model_check.mp.solutions.pose,'Pose',return_value=pose), \
             patch.object(model_check,'VRChatOSCBackend',return_value=backend):
            with self.assertRaisesRegex(ValueError,'Nenhuma pose'):model_check.validate('pose','hand')
        pose.__exit__.assert_called_once();backend.disconnect.assert_called_once()

    def test_positive_contract_with_mock_inference_and_real_udp(self):
        from unittest.mock import MagicMock
        world,image,_=body()
        pose=MagicMock();pose.__enter__.return_value.process.return_value=NS(
            pose_world_landmarks=NS(landmark=world),pose_landmarks=NS(landmark=image))
        hands=MagicMock();hands.__enter__.return_value.process.return_value=detection()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture';path.write_bytes(b'fixture')
            with patch.object(model_check,'read_rgb',return_value=np.zeros((120,160,3),np.uint8)), \
                 patch.object(model_check.mp.solutions.pose,'Pose',return_value=pose), \
                 patch.object(model_check.mp.solutions.hands,'Hands',return_value=hands):
                result=model_check.validate(path,path)
        self.assertEqual(result['body_addresses'],17)
        self.assertEqual(result['hand_addresses'],12)
        self.assertEqual(result['hand_confirmation_states'],[[],['Left'],['Left']])
        self.assertFalse(result['vrchat_tested'])
        pose.__exit__.assert_called_once();hands.__exit__.assert_called_once()
