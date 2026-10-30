"""Observação temporal sem publicar poses, clicar ou alterar rastreamento."""
import io
import math
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import steamvr_hands_check as check
from steamvr_protocol import SteamVRHandsClient,control,DriverConnectionError


def status(mask=0):return {'protocol':1,'tracked_mask':mask,'hmd_valid':True}


class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class LiveStatusTests(unittest.TestCase):
    def test_transient_both_hands_preserved_in_summary_after_loss(self):
        clock=Clock();client=Mock();client.status.side_effect=[status(3),status(),status(),status()]
        with patch('sys.stdout',new_callable=io.StringIO):
            result=check.watch_status(client,1.,status(),clock=clock,sleep=clock.sleep)
        self.assertEqual(result['observed_masks'],[0,3])
        self.assertEqual(result['samples_with_both_hands'],1)
        self.assertEqual(result['samples'],5)
        client.confirm.assert_not_called();client.send.assert_not_called();client.invalidate.assert_not_called()

    def test_separate_hands_never_reported_as_simultaneous(self):
        clock=Clock();client=Mock();client.status.side_effect=[status(1),status(2),status(1),status(2)]
        with patch('sys.stdout',new_callable=io.StringIO):
            result=check.watch_status(client,1.,status(),clock=clock,sleep=clock.sleep)
        self.assertEqual(result['observed_masks'],[0,1,2])
        self.assertEqual(result['samples_with_both_hands'],0)

    def test_constant_status_printed_once_and_short_watch_is_bounded(self):
        clock=Clock();client=Mock();client.status.return_value=status()
        with patch('sys.stdout',new_callable=io.StringIO) as output:
            result=check.watch_status(client,.1,status(),clock=clock,sleep=clock.sleep)
        self.assertEqual(len(output.getvalue().splitlines()),1)
        self.assertEqual(clock.now,.1);self.assertEqual(result['samples'],1)
        client.status.assert_not_called()

    def test_interruption_reports_partial_summary(self):
        clock=Clock();client=Mock()
        with patch('sys.stdout',new_callable=io.StringIO):
            result=check.watch_status(client,10,status(3),clock=clock,sleep=Mock(side_effect=KeyboardInterrupt))
        self.assertTrue(result['cancelled']);self.assertEqual(result['samples_with_both_hands'],1)

    def test_invalid_duration_and_conflicting_cli_do_not_open_socket(self):
        for seconds in (0,-1,31,math.nan,math.inf,True,'10'):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):
                check.watch_status(Mock(),seconds,status())
        for arguments in (['--watch','0'],['--watch','nan'],['--watch','31'],['--watch','10','--confirm']):
            with self.subTest(arguments=arguments),patch.object(check,'SteamVRHandsClient') as client,patch('sys.stderr',new_callable=io.StringIO):
                with self.assertRaises(SystemExit):check.main(arguments)
                client.assert_not_called()

    def test_cli_closes_socket_and_never_confirms(self):
        with patch.object(check,'SteamVRHandsClient') as factory,patch.object(check,'watch_status',return_value={'samples':1}) as watch,patch('sys.stdout',new_callable=io.StringIO):
            client=factory.return_value;client.status.return_value=status()
            check.main(['--watch','10'])
            watch.assert_called_once_with(client,10.,status())
        client.close.assert_called_once();client.confirm.assert_not_called()

    def test_network_failure_in_watch_closes_socket_and_is_reported(self):
        with patch.object(check,'SteamVRHandsClient') as factory,patch.object(check,'watch_status',side_effect=DriverConnectionError('lost')),patch('sys.stdout',new_callable=io.StringIO),patch('sys.stderr',new_callable=io.StringIO) as output:
            client=factory.return_value;client.status.return_value=status()
            with self.assertRaises(SystemExit) as error:check.main(['--watch','10'])
            self.assertEqual(error.exception.code,2);self.assertIn('lost',output.getvalue())
        client.close.assert_called_once();client.confirm.assert_not_called()

    def test_real_udp_watch_only_sends_status_requests(self):
        packets=[];errors=[]
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(2)
            def peer():
                try:
                    for mask in (0,1,2,3,0):
                        packet,address=receiver.recvfrom(2048);packets.append(packet)
                        receiver.sendto(struct.pack('<8sIII',b'MPVRA001',1,mask,1),address)
                except OSError as exc:errors.append(exc)
            thread=threading.Thread(target=peer);thread.start()
            client=SteamVRHandsClient(receiver.getsockname()[1],timeout=1)
            try:
                clock=Clock()
                with patch('sys.stdout',new_callable=io.StringIO):
                    result=check.watch_status(client,1.,client.status(),clock=clock,sleep=clock.sleep)
            finally:client.close();thread.join(timeout=3)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(packets,[control(2)]*5)
        self.assertEqual(result['observed_masks'],[0,1,2,3])
        self.assertEqual(result['samples_with_both_hands'],1)


if __name__=='__main__':unittest.main()
