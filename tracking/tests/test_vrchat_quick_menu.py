"""Comandos oficiais OSC de menu: sem SteamVR ou VRChat instalados no runner."""
import io
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock,patch

from pythonosc.osc_packet import OscPacket
from pythonosc.udp_client import SimpleUDPClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import vrchat_desktop_check as tool


class QuickMenuTests(unittest.TestCase):
    def test_real_udp_for_both_menu_sides_in_order_with_integer_buttons(self):
        for command in ('menu-left','menu-right','use-left','use-right'):
            with self.subTest(command=command),socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
                receiver.bind(('127.0.0.1',0));receiver.settimeout(2)
                client=SimpleUDPClient(*receiver.getsockname())
                try:
                    tool.send_button(client,tool.COMMANDS[command][0],sleep=lambda seconds:None)
                    for expected in (0,1,0):
                        message=OscPacket(receiver.recv(4096)).messages[0].message
                        self.assertEqual(message.address,tool.COMMANDS[command][0])
                        self.assertEqual(message.params,[expected])
                        self.assertIs(type(message.params[0]),int)
                finally:client.close()

    def test_menu_preview_does_not_sleep_or_open_socket(self):
        with patch.object(tool,'SimpleUDPClient') as client,patch.object(tool.time,'sleep') as sleep,patch('sys.stdout',new_callable=io.StringIO) as output:
            tool.main(['--command','menu-left','--delay','3'])
            self.assertIn('/input/QuickMenuToggleLeft 0 -> 1 -> 0',output.getvalue())
            client.assert_not_called();sleep.assert_not_called()

    def test_delayed_menu_send_closes_socket_and_jump_remains_default(self):
        for command,address in (('menu-left','/input/QuickMenuToggleLeft'),('menu-right','/input/QuickMenuToggleRight'),('use-left','/input/UseLeft'),('use-right','/input/UseRight'),('jump','/input/Jump')):
            with self.subTest(command=command),patch.object(tool,'SimpleUDPClient') as client,patch.object(tool.time,'sleep') as sleep,patch.object(tool,'send_button') as send,patch('sys.stdout',new_callable=io.StringIO):
                arguments=['--send','--delay','3']
                if command!='jump':arguments+=['--command',command]
                tool.main(arguments)
                sleep.assert_called_once_with(3.)
                send.assert_called_once_with(client.return_value,address)
                client.return_value.close.assert_called_once()

    def test_use_preview_reports_real_endpoint_without_sending(self):
        for side in ('left','right'):
            with self.subTest(side=side),patch.object(tool,'SimpleUDPClient') as client,patch('sys.stdout',new_callable=io.StringIO) as output:
                tool.main(['--command','use-'+side])
                self.assertIn('/input/Use'+side.title()+' 0 -> 1 -> 0',output.getvalue())
                client.assert_not_called()

    def test_use_release_after_interruption(self):
        for side in ('Left','Right'):
            client=Mock()
            with self.subTest(side=side),self.assertRaises(KeyboardInterrupt):
                tool.send_button(client,'/input/Use'+side,sleep=Mock(side_effect=KeyboardInterrupt))
            client.send_message.assert_called_with('/input/Use'+side,0)

    def test_invalid_command_delay_and_port_never_create_client(self):
        for arguments in (['--command','unknown'],['--port','65536'],['--delay','-1'],['--delay','31'],['--delay','nan'],['--delay','inf']):
            with self.subTest(arguments=arguments),patch.object(tool,'SimpleUDPClient') as client,patch('sys.stderr',new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as error:tool.main(['--send']+arguments)
                self.assertEqual(error.exception.code,2);client.assert_not_called()

    def test_release_on_failed_press_or_interrupted_pulse(self):
        for failure in (OSError('failed send'),KeyboardInterrupt()):
            client=Mock()
            if isinstance(failure,OSError):client.send_message.side_effect=[None,failure,None]
            sleep=Mock(side_effect=failure) if isinstance(failure,KeyboardInterrupt) else Mock()
            with self.subTest(failure=type(failure).__name__),self.assertRaises(type(failure)):
                tool.send_button(client,'/input/QuickMenuToggleLeft',sleep=sleep)
            client.send_message.assert_called_with('/input/QuickMenuToggleLeft',0)

    def test_unknown_address_never_sent(self):
        client=Mock()
        with self.assertRaises(ValueError):tool.send_button(client,'/input/Invented')
        client.send_message.assert_not_called()

    def test_delay_interruption_does_not_create_or_send(self):
        with patch.object(tool,'SimpleUDPClient') as client,patch.object(tool.time,'sleep',side_effect=KeyboardInterrupt),patch('sys.stdout',new_callable=io.StringIO):
            with self.assertRaises(KeyboardInterrupt):tool.main(['--send','--delay','3'])
            client.assert_not_called()

    def test_send_error_is_reported_and_socket_closed(self):
        with patch.object(tool,'SimpleUDPClient') as client,patch.object(tool,'send_button',side_effect=OSError('offline')),patch('sys.stderr',new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as error:tool.main(['--send','--command','menu-right'])
            self.assertEqual(error.exception.code,2)
            self.assertIn('Falha ao enviar OSC',output.getvalue())
            client.return_value.close.assert_called_once()


if __name__=='__main__':unittest.main()
