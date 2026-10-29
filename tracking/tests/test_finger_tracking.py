"""Cálculos, MediaPipe real, UDP real e regressões sem webcam."""
import math
import socket
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import numpy as np
import mediapipe as mp
from pythonosc.udp_client import UDPClient
from pythonosc.osc_packet import OscPacket
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from finger_tracking import FingerTracking, FINGERS, finger_curls, draw_hands
from hand_quality import HandQualitySettings
from test_first_improvement import run_one_frame
import mediapipepose as app


def landmarks(bent=False):
    p = [NS(x=.35,y=.65,z=0.) for _ in range(21)]
    for index, chain in enumerate(FINGERS.values()):
        xy = [(0,0),(1,0),(1,1),(0,1)] if bent else [(0,0),(1,0),(2,0),(3,0)]
        for key, (x,y) in zip(chain, xy):
            p[key] = NS(x=y*.03+.15+index*.1, y=-x*.03+.45, z=0.)
    return p


def detection():
    hand = NS(landmark=landmarks())
    return NS(multi_hand_landmarks=[hand], multi_hand_world_landmarks=[hand],
              multi_handedness=[NS(classification=[NS(label='Left',score=.9)])])


def empty():
    return NS(multi_hand_landmarks=None,multi_hand_world_landmarks=None,multi_handedness=None)


class CurlTests(unittest.TestCase):
    def test_five_fingers_open_and_closed(self):
        self.assertEqual(set(finger_curls(landmarks())), set(FINGERS))
        for v in finger_curls(landmarks()).values():
            self.assertAlmostEqual(v, 0.)
        for v in finger_curls(landmarks(True)).values():
            self.assertAlmostEqual(v, 1.)

    def test_translation_rotation_scale(self):
        p = landmarks(True)
        for v in p:
            v.x,v.y,v.z = -v.y*2+4,v.x*2-1,v.z*2+3
        for v in finger_curls(p).values():
            self.assertAlmostEqual(v, 1.)

    def test_invalid_and_degenerate(self):
        for p in (landmarks()[:20], [NS(x=0,y=0,z=0)]*21):
            with self.assertRaises(ValueError):
                finger_curls(p)
        for value in (math.nan,math.inf):
            p = landmarks()
            p[3].x = value
            with self.assertRaises(ValueError):
                finger_curls(p)


class FingerTests(unittest.TestCase):
    def make(self, result=None, client=None):
        detector = Mock()
        detector.process.return_value = result if result is not None else detection()
        return FingerTracking(detector, client, HandQualitySettings(min_handedness=.5, min_palm_pixels=0, confirmation_frames=1))

    def test_mirroring_and_original_preserved(self):
        rgb = np.arange(6*8*3,dtype=np.uint8).reshape((6,8,3))
        original = rgb.copy()
        for mirrored in (False,True):
            tracker = self.make()
            frames = tracker.process(rgb, mirrored)
            self.assertIn('Left', frames)
            expected = rgb if mirrored else rgb[:,::-1]
            np.testing.assert_array_equal(tracker.detector.process.call_args.args[0], expected)
            self.assertAlmostEqual(frames['Left'].points[0,0], .35 if mirrored else .65)
        np.testing.assert_array_equal(rgb,original)

    def test_bad_confidence_label_and_coordinates(self):
        for field,value in (('score',.1),('score',math.nan),('label','Unknown')):
            result = detection()
            setattr(result.multi_handedness[0].classification[0],field,value)
            self.assertFalse(self.make(result).process(np.zeros((16,16,3),np.uint8)))
        result = detection()
        result.multi_hand_landmarks[0].landmark[0].x = 2
        self.assertFalse(self.make(result).process(np.zeros((16,16,3),np.uint8)))

    def test_loss_recovery_and_invalid_hand(self):
        tracker = self.make()
        image = np.zeros((16,16,3),np.uint8)
        self.assertTrue(tracker.process(image))
        tracker.detector.process.return_value = empty()
        self.assertFalse(tracker.process(image))
        tracker.detector.process.return_value = detection()
        self.assertTrue(tracker.process(image))
        tracker.detector.process.return_value.multi_hand_world_landmarks[0].landmark[1].x = math.nan
        self.assertFalse(tracker.process(image))

    def test_pause_resume_reset_close(self):
        tracker = self.make(client=Mock())
        image = np.zeros((16,16,3),np.uint8)
        tracker.process(image)
        tracker.suspend()
        calls = tracker.client.send.call_count
        tracker.suspend()
        self.assertEqual(tracker.client.send.call_count,calls)
        tracker.process(image)
        tracker.suspend()
        self.assertEqual(tracker.client.send.call_count,calls+2)
        tracker.reset()
        tracker.detector.reset.assert_called_once()
        tracker.close()
        tracker.detector.close.assert_called_once()

    def test_send_error_still_closes(self):
        tracker = self.make(client=Mock())
        tracker.client.send.side_effect = OSError('network')
        with self.assertRaises(OSError):
            tracker.close()
        tracker.detector.close.assert_called_once()

    def test_real_udp_floats_and_missing_flags(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0))
            receiver.settimeout(2)
            tracker = self.make(client=UDPClient(*receiver.getsockname()))
            self.addCleanup(tracker.client.close)
            tracker.process(np.zeros((16,16,3),np.uint8))
            values = {m.message.address:m.message.params[0] for m in OscPacket(receiver.recv(65535)).messages}
            self.assertTrue(values['/avatar/parameters/MP_Left_Tracked'])
            self.assertFalse(values['/avatar/parameters/MP_Right_Tracked'])
            for name in FINGERS:
                self.assertAlmostEqual(values[f'/avatar/parameters/MP_Left_{name}'],0.)
            tracker.suspend()
            values = {m.message.address:m.message.params[0] for m in OscPacket(receiver.recv(65535)).messages}
            self.assertEqual(set(values.values()),{False})

    def test_real_model_sequential_frames(self):
        with mp.solutions.hands.Hands(max_num_hands=2) as detector:
            tracker = FingerTracking(detector)
            for _ in range(3):
                self.assertEqual(tracker.process(np.zeros((120,160,3),np.uint8)),{})
            tracker.reset()
            self.assertEqual(tracker.process(np.zeros((120,160,3),np.uint8)),{})

    def test_main_without_body_and_resource_release(self):
        detector = Mock()
        detector.process.return_value = detection()
        with patch.object(app.mp.solutions.hands,'Hands',return_value=detector):
            backend = run_one_frame(app,False,parameter_overrides={'track_fingers':True, 'hand_quality':HandQualitySettings(min_palm_pixels=0,confirmation_frames=1)})
        backend.updatepose.assert_not_called()
        self.assertIn('Left',backend.test_params.finger_frames)
        self.assertGreater(backend.test_params.finger_timestamp_ms,0)
        detector.close.assert_called_once()
        backend.client.send.assert_called()

    def test_drawing_without_body(self):
        rgb = np.zeros((80,120,3),np.uint8)
        draw_hands(rgb,self.make().process(rgb))
        self.assertTrue(rgb.any())

    def test_two_hands_and_duplicate_side_selection(self):
        result = detection()
        second = detection()
        second.multi_handedness[0].classification[0].label = 'Right'
        result.multi_hand_landmarks += second.multi_hand_landmarks
        result.multi_hand_world_landmarks += second.multi_hand_world_landmarks
        result.multi_handedness += second.multi_handedness
        self.assertEqual(set(self.make(result).process(np.zeros((16,16,3),np.uint8))), {'Left','Right'})
        result.multi_handedness[1].classification[0].label = 'Left'
        result.multi_handedness[1].classification[0].score = .99
        frames = self.make(result).process(np.zeros((16,16,3),np.uint8))
        self.assertEqual(frames, {})  # Duas mãos com mesmo lado: ambiguidade rejeitada.

    def test_processing_error_releases_real_pipeline_resources(self):
        detector = Mock()
        detector.process.side_effect = RuntimeError('inference failed')
        with patch.object(app.mp.solutions.hands,'Hands',return_value=detector):
            with self.assertRaisesRegex(RuntimeError, 'inference failed'):
                run_one_frame(app,False,parameter_overrides={'track_fingers':True, 'hand_quality':HandQualitySettings(min_palm_pixels=0,confirmation_frames=1)})
        detector.close.assert_called_once()

    def test_disabled_does_not_construct_hands(self):
        with patch.object(app.mp.solutions.hands,'Hands') as factory:
            run_one_frame(app,True)
        factory.assert_not_called()

    def test_real_video_sequential_timestamps_and_hands(self):
        import cv2
        import tempfile
        from video_source import VideoFileSource
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'hands.avi')
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), 25, (160,120))
            self.assertTrue(writer.isOpened())
            try:
                for _ in range(3):
                    writer.write(np.zeros((120,160,3), np.uint8))
            finally:
                writer.release()
            source = VideoFileSource(path, pace=False)
            timestamps, indices = [], []
            try:
                source.start()
                with mp.solutions.hands.Hands(max_num_hands=2) as detector:
                    tracker = FingerTracking(detector)
                    while True:
                        frame = source.read_latest()
                        if frame is None:
                            break
                        timestamps.append(source.timestamp_ms)
                        indices.append(source.index)
                        self.assertFalse(tracker.process(cv2.cvtColor(frame[0],cv2.COLOR_BGR2RGB)))
            finally:
                source.close()
            self.assertEqual(indices, [0,1,2])
            np.testing.assert_allclose(timestamps, [0,40,80])
            self.assertIsNone(source.cap)
