import math
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
from pythonosc.osc_packet import OscPacket
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from freshness import FrameFreshness
from desktop_osc import VRChatDesktopBackend
from finger_tracking import FingerTracking, HandFrame, FINGERS
from test_desktop_osc import points


class InvalidTrackingTests(unittest.TestCase):
    def test_expiry_once_per_gap_and_recovery(self):
        state=FrameFreshness()
        self.assertFalse(state.expire(10))
        state.touch(10)
        self.assertFalse(state.expire(11.99))
        self.assertTrue(state.expire(12))
        self.assertFalse(state.expire(13))
        state.touch(14)
        self.assertTrue(state.expire(16))

    def test_invalid_timeouts(self):
        for value in (-1,0,math.nan,math.inf):
            with self.assertRaises(ValueError):FrameFreshness(value)

    def test_recovered_raised_arms_cannot_retrigger(self):
        backend=VRChatDesktopBackend();backend.client=Mock()
        for timestamp in (0,.1,.2):backend.process_image(points(),timestamp)
        backend.process_image(None,.3)
        backend.client.send_message.reset_mock()
        for timestamp in (.4,.5,.6,.7):backend.process_image(points(),timestamp)
        backend.client.send_message.assert_not_called()
        backend.process_image(points(False),.8)
        for timestamp in (.9,1.,1.1):backend.process_image(points(),timestamp)
        backend.client.send_message.assert_called_once_with('/input/Jump',1)

    def test_button_release_does_not_require_new_image(self):
        backend=VRChatDesktopBackend();backend.client=Mock()
        for timestamp in (0,.01,.02):backend.process_image(points(),timestamp)
        backend.tick(.18)
        backend.client.send_message.assert_called_with('/input/Jump',0)
        self.assertFalse(backend.pressed)

    def test_invalid_curls_send_only_missing_flag(self):
        for bad in (math.nan,math.inf,-.1,1.1,True,'invalid'):
            client=Mock();tracker=FingerTracking(None,client)
            curls=dict.fromkeys(FINGERS,.5);curls['Index']=bad
            tracker.publish({'Left':HandFrame('Left',1,np.zeros((21,3)),curls)})
            values={m.message.address:m.message.params[0] for m in OscPacket(client.send.call_args.args[0].dgram).messages}
            self.assertEqual(values,{'/avatar/parameters/MP_Left_Tracked':False,'/avatar/parameters/MP_Right_Tracked':False})

    def test_incomplete_or_wrong_side_hand_is_not_published(self):
        for frame in (HandFrame('Right',1,None,dict.fromkeys(FINGERS,.5)),HandFrame('Left',1,None,{'Index':.5})):
            client=Mock();FingerTracking(None,client).publish({'Left':frame})
            values={m.message.address:m.message.params[0] for m in OscPacket(client.send.call_args.args[0].dgram).messages}
            self.assertFalse(values['/avatar/parameters/MP_Left_Tracked'])

    def test_valid_hand_preserves_each_finger(self):
        client=Mock();curls=dict(zip(FINGERS,[0.,.25,.5,.75,1.]))
        FingerTracking(None,client).publish({'Right':HandFrame('Right',1,None,curls)})
        values={m.message.address:m.message.params[0] for m in OscPacket(client.send.call_args.args[0].dgram).messages}
        for key,value in curls.items():self.assertEqual(values['/avatar/parameters/MP_Right_'+key],value)

    def test_pause_reset_requires_neutral_pose_before_new_action(self):
        backend=VRChatDesktopBackend();backend.client=Mock()
        for timestamp in (0,.1,.2):backend.process_image(points(),timestamp)
        backend.reset()
        backend.client.send_message.reset_mock()
        for timestamp in (.3,.4,.5):backend.process_image(points(),timestamp)
        backend.client.send_message.assert_not_called()
        backend.process_image(points(False),.6)
        for timestamp in (.7,.8,.9):backend.process_image(points(),timestamp)
        backend.client.send_message.assert_called_once_with('/input/Jump',1)
