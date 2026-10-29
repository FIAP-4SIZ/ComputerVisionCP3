"""A tradução deve preservar os controles e o contrato HTTP/OSC."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import webui
from finger_tracking import FingerTracking
from test_finger_tracking import empty
from video_source import VideoFileSource
from scrollable_panel import ScrollablePanel


class PortugueseUITests(unittest.TestCase):
    def test_web_page_in_portuguese_and_numeric_control(self):
        params = NS(additional_smoothing=.5, change_additional_smoothing=Mock())
        with patch.object(webui,'params',params):
            client = webui.app.test_client()
            response = client.get('/')
            self.assertEqual(response.status_code,200)
            text = response.get_data(as_text=True)
            for label in ('lang="pt-BR"','Ajustar rotação','Recalibrar','Suavização adicional'):
                self.assertIn(label,text)
            self.assertNotIn('Hello',text)
            self.assertEqual(client.post('/smoothing',data={'action':'Atualizar','value':'.7'}).status_code,302)
            params.change_additional_smoothing.assert_called_once_with(.7,paramid=1)

    def test_web_rotations_and_scale_keep_existing_routes(self):
        params = NS(euler_rot_y=0,euler_rot_x=90,euler_rot_z=180,posescale=1,
                    rot_change_y=Mock(),rot_change_x=Mock(),rot_change_z=Mock(),change_scale=Mock(),gui=Mock())
        with patch.object(webui,'params',params):
            client = webui.app.test_client()
            for path in ('/roty','/rotx','/rotz','/scale'):
                self.assertEqual(client.post(path,data={'action':'>'}).status_code,302)
            self.assertEqual(client.post('/autocalib').status_code,302)
        params.rot_change_y.assert_called_once_with(1)
        params.rot_change_x.assert_called_once_with(91)
        params.rot_change_z.assert_called_once_with(181)
        params.change_scale.assert_called_once_with(1.01)
        params.gui.autocalibrate.assert_called_once()

    def test_video_status_translates_only_display_state(self):
        source = VideoFileSource.__new__(VideoFileSource)
        source.total,source.index,source.timestamp_ms,source.timestamp_estimated,source.error = 10,2,80,False,''
        for state,label in (('running','Em andamento'),('paused','Pausado'),('completed','Concluido')):
            source.state=state
            self.assertIn(label,source.status)
            self.assertEqual(source.state,state)

    def test_scroll_mouse_wheel_and_trackpad_directions(self):
        panel = NS(canvas=Mock())
        for delta,units in ((120,-1),(-120,1),(1,-1),(-1,1),(240,-2)):
            ScrollablePanel._wheel(panel,NS(delta=delta))
            panel.canvas.yview_scroll.assert_called_with(units,'units')
        panel.canvas.reset_mock()
        ScrollablePanel._wheel(panel,NS(delta=0))
        panel.canvas.yview_scroll.assert_not_called()
