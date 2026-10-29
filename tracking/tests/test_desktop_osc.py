import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from desktop_osc import VRChatDesktopBackend
from test_first_improvement import run_one_frame
import mediapipepose as app


def points(up=True):
    p=[NS(x=.5,y=.6,z=0.,visibility=1.) for _ in range(33)]
    p[15].y=p[16].y=.3 if up else .8
    for i in range(23,33): p[i].visibility=0.
    return p


class DesktopTests(unittest.TestCase):
    def backend(self):
        b=VRChatDesktopBackend();b.client=Mock();return b

    def test_chest_three_frames_one_pulse_and_rearm(self):
        b=self.backend()
        for t in (0,.04): b.process_image(points(),t)
        b.client.send_message.assert_not_called()
        b.process_image(points(),.08)
        b.client.send_message.assert_called_once_with('/input/Jump',1)
        b.process_image(points(),.3)
        b.client.send_message.assert_called_with('/input/Jump',0)
        for t in (.4,.5,.6): b.process_image(points(),t)
        self.assertEqual(b.client.send_message.call_count,2)
        b.process_image(points(False),.7)
        for t in (.8,.9,1.): b.process_image(points(),t)
        self.assertEqual(b.client.send_message.call_count,3)

    def test_missing_occluded_outside_reset_and_release(self):
        for invalid in (None,points()):
            b=self.backend()
            for t in (0,.01,.02): b.process_image(points(),t)
            if invalid is not None: invalid[15].x=2
            b.process_image(invalid,.03)
            b.client.send_message.assert_called_with('/input/Jump',0)
            self.assertFalse(b.pressed)

    def test_pause_disconnect_release_without_repeated_packets(self):
        b=self.backend()
        for t in (0,.01,.02): b.process_image(points(),t)
        b.reset();b.disconnect();b.reset()
        self.assertEqual(b.client.send_message.call_count,2)

    def test_main_routes_image_without_body_trackers(self):
        b=run_one_frame(app,False,parameter_overrides={'backend':3})
        b.process_image.assert_called_once()
        b.disconnect.assert_called_once()

    def test_real_udp_probe_uses_integer_button_and_releases(self):
        import socket
        from pythonosc.udp_client import SimpleUDPClient
        from pythonosc.osc_packet import OscPacket
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
        from vrchat_desktop_check import send_jump
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(2)
            send_jump(SimpleUDPClient(*receiver.getsockname()),sleep=lambda seconds:None)
            for expected in (0,1,0):
                message=OscPacket(receiver.recv(4096)).messages[0].message
                self.assertEqual(message.address,'/input/Jump')
                self.assertEqual(message.params,[expected])
                self.assertIs(type(message.params[0]),int)

    def test_probe_preview_and_invalid_port_do_not_send(self):
        from unittest.mock import patch
        import vrchat_desktop_check as tool
        with patch.object(tool,'SimpleUDPClient') as client:
            tool.main([])
            with self.assertRaises(SystemExit): tool.main(['--send','--port','0'])
        client.assert_not_called()

    def test_probe_releases_after_interruption(self):
        import vrchat_desktop_check as tool
        client=Mock()
        with self.assertRaises(KeyboardInterrupt):
            tool.send_jump(client,sleep=Mock(side_effect=KeyboardInterrupt))
        client.send_message.assert_called_with('/input/Jump',0)

    def test_preview_supports_windows_cp1252_console(self):
        import io
        from contextlib import redirect_stdout
        import vrchat_desktop_check as tool
        buffer=io.BytesIO()
        console=io.TextIOWrapper(buffer,encoding='cp1252')
        with redirect_stdout(console): tool.main([])
        console.flush()
        self.assertIn('0 -> 1 -> 0',buffer.getvalue().decode('cp1252'))
