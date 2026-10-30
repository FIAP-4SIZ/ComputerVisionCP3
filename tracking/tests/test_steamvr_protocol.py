"""Contrato nativo de mãos: encoder, erros, controle e socket UDP real."""
import math
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from steamvr_protocol import (PACKET_SIZE,DriverConnectionError,encode_frame,
                             control,decode_status,decode_head_pose,SteamVRHandsClient)


def geometry():
    return [.1,.2,-.3,1,0,0,0],[[0,0,0,1,0,0,0] for _ in range(31)]


class SteamVRProtocolTests(unittest.TestCase):
    def test_fixed_layout_and_float_values(self):
        pose,bones=geometry()
        data=encode_frame(1,17,pose,bones)
        self.assertEqual(len(data),PACKET_SIZE)
        self.assertEqual(struct.unpack('<8sIII',data[:20]),(b'MPVRH001',1,17,1))
        for actual,expected in zip(struct.unpack('<7f',data[20:48]),pose):self.assertAlmostEqual(actual,expected)

    def test_loss_does_not_require_or_publish_fake_geometry(self):
        data=encode_frame(0,18,valid=False)
        self.assertEqual(struct.unpack('<8sIII',data[:20]),(b'MPVRH001',0,18,0))
        self.assertEqual(data[20:],bytes(PACKET_SIZE-20))

    def test_invalid_side_sequence_flags(self):
        for side,seq,valid in ((2,1,False),(True,1,False),(0,-1,False),(0,2**32,False),(0,True,False),(0,1,1)):
            with self.assertRaises(ValueError):encode_frame(side,seq,valid=valid)

    def test_invalid_positions_quaternions_and_root(self):
        for bad in (math.nan,math.inf,11,True,'1',10**1000):
            pose,bones=geometry();pose[0]=bad
            with self.subTest(bad=str(bad)[:20]),self.assertRaises(ValueError):encode_frame(0,1,pose,bones)
        pose,bones=geometry();pose[3:]=[0,0,0,0]
        with self.assertRaises(ValueError):encode_frame(0,1,pose,bones)
        for index,value in ((0,.01),(4,.1)):
            pose,bones=geometry();bones[0][index]=value
            with self.assertRaises(ValueError):encode_frame(0,1,pose,bones)
        pose,bones=geometry();bones[5][0]=1.1
        with self.assertRaises(ValueError):encode_frame(0,1,pose,bones)

    def test_missing_or_malformed_geometry(self):
        pose,bones=geometry()
        for p,b in ((None,bones),(pose,None),(pose,bones[:30]),(pose[:6],bones),(pose,[[0]*7]*31)):
            with self.assertRaises(ValueError):encode_frame(0,1,p,b)

    def test_commands_are_explicit_and_bounded(self):
        self.assertEqual(struct.unpack('<8sII',control(1,300)),(b'MPVRC001',1,300))
        for cmd,value in ((0,0),(1,501),(1,-1),(2,1),(True,0)):
            with self.assertRaises(ValueError):control(cmd,value)

    def test_status_version_mask_hmd_validation(self):
        self.assertEqual(decode_status(struct.pack('<8sIII',b'MPVRA001',1,3,1)),dict(protocol=1,tracked_mask=3,hmd_valid=True))
        for packet in (b'',struct.pack('<8sIII',b'MPVRA001',2,3,1),struct.pack('<8sIII',b'MPVRA001',1,4,1),struct.pack('<8sIII',b'MPVRA001',1,3,2)):
            with self.assertRaises(DriverConnectionError):decode_status(packet)

    def test_head_matrix_query_decodes_only_valid_finite_pose(self):
        matrix=[1,0,0,0,0,1,0,1.7,0,0,1,0]
        packet=struct.pack('<8sI12f',b'MPVRP001',1,*matrix)
        self.assertAlmostEqual(decode_head_pose(packet)[1][3],1.7,places=6)
        self.assertEqual(control(3),struct.pack('<8sII',b'MPVRC001',3,0))
        for invalid in (packet[:-1],struct.pack('<8sI12f',b'MPVRP001',0,*matrix),struct.pack('<8sI12f',b'MPVRP001',1,*([math.nan]*12))):
            with self.assertRaises(DriverConnectionError):decode_head_pose(invalid)

    def test_head_pose_client_requests_native_matrix(self):
        matrix=[1,0,0,0,0,1,0,1.7,0,0,1,0]
        with patch('steamvr_protocol.socket.socket') as factory:
            client=SteamVRHandsClient();client.socket.recv.return_value=struct.pack('<8sI12f',b'MPVRP001',1,*matrix)
            self.assertAlmostEqual(client.head_pose()[1][3],1.7,places=6)
            client.socket.send.assert_called_once_with(control(3));client.close()

    def test_real_udp_client_handshake_data_and_controls(self):
        captured=[]
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(2)
            def peer():
                packet,address=receiver.recvfrom(2048);captured.append(packet)
                receiver.sendto(struct.pack('<8sIII',b'MPVRA001',1,0,1),address)
                for _ in range(4):captured.append(receiver.recvfrom(2048)[0])
            thread=threading.Thread(target=peer);thread.start()
            client=SteamVRHandsClient(receiver.getsockname()[1])
            try:
                self.assertTrue(client.status()['hmd_valid'])
                pose,bones=geometry();client.send(0,pose,bones);client.confirm();client.invalidate()
            finally:
                client.close();thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(captured),5)
        self.assertEqual(captured[0],control(2))
        self.assertEqual(captured[2],control(1,300))
        self.assertEqual([struct.unpack('<8sIII',p[:20])[3] for p in (captured[1],captured[3],captured[4])],[1,0,0])

    def test_status_timeout_becomes_actionable_error(self):
        with patch('steamvr_protocol.socket.socket') as factory:
            factory.return_value.recv.side_effect=socket.timeout('timeout')
            client=SteamVRHandsClient()
            with self.assertRaisesRegex(DriverConnectionError,'Inicie SteamVR'):client.status()
            client.close()
        factory.return_value.close.assert_called_once()

    def test_client_closes_if_setup_fails(self):
        with patch('steamvr_protocol.socket.socket') as factory:
            factory.return_value.connect.side_effect=OSError('failed')
            with self.assertRaises(OSError):SteamVRHandsClient()
        factory.return_value.close.assert_called_once()

    def test_sequence_remains_ordered_within_same_millisecond(self):
        with patch('steamvr_protocol.socket.socket'),patch('steamvr_protocol.time.monotonic',return_value=1):
            client=SteamVRHandsClient();client.send(0,valid=False);client.send(0,valid=False)
            packets=[call.args[0] for call in client.socket.send.call_args_list]
            self.assertEqual([struct.unpack('<I',p[12:16])[0] for p in packets],[1000,1001])
            client.close()

    def test_invalid_port_does_not_open_socket(self):
        for port in (0,65536,True,'39570'):
            with patch('steamvr_protocol.socket.socket') as factory,self.assertRaises(ValueError):SteamVRHandsClient(port)
            factory.assert_not_called()
