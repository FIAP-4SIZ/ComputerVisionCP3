import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from helpers import CameraStream,CameraInputError
import inference_gui
from test_first_improvement import run_one_frame
import mediapipepose as app


def params(camera='0'):
    return NS(cameraid=camera,camera_settings=False,camera_height=480,camera_width=640,exit_ready=False)


def cap(reads):
    c=Mock();c.isOpened.return_value=True;c.read.side_effect=reads;return c


class CaptureLifecycleTests(unittest.TestCase):
    def test_valid_first_frame_published_before_thread(self):
        image=np.zeros((10,12,3),np.uint8);c=cap([(True,image)])
        with patch('helpers.cv2.VideoCapture',return_value=c),patch('helpers.threading.Thread') as thread:
            camera=CameraStream(params())
            np.testing.assert_array_equal(camera.read_latest()[0],image)
            thread.return_value.start.assert_called_once()
            camera.close()
        c.release.assert_called_once()

    def test_windows_fallback_same_id_after_failed_reads(self):
        bad=cap([(False,None)]*5);good=cap([(True,np.zeros((4,4,3),np.uint8))])
        with patch('helpers.platform','win32'),patch('helpers.cv2.VideoCapture',side_effect=[bad,good]) as factory,patch('helpers.threading.Thread'):
            camera=CameraStream(params())
            self.assertEqual([c.args[0] for c in factory.call_args_list],[0,0])
            bad.release.assert_called_once()
            self.assertTrue(camera.image_ready)
            camera.close()

    def test_ip_failure_releases_without_scanning_devices(self):
        bad=cap([(False,None)]*5)
        with patch('helpers.platform','win32'),patch('helpers.cv2.VideoCapture',return_value=bad) as factory,patch('helpers.threading.Thread') as thread:
            with self.assertRaises(CameraInputError):CameraStream(params('http://camera/video'))
            self.assertEqual(factory.call_count,1)
            thread.assert_not_called()
        bad.release.assert_called_once()

    def test_open_failure_and_invalid_frame_never_start_capture(self):
        for opened,reads in ((False,[]),(True,[(True,np.zeros((2,2),np.uint8))]*5)):
            c=cap(reads);c.isOpened.return_value=opened
            with patch('helpers.platform','linux'),patch('helpers.cv2.VideoCapture',return_value=c),patch('helpers.threading.Thread') as thread:
                with self.assertRaises(CameraInputError): CameraStream(params())
                thread.assert_not_called()
            c.release.assert_called_once()

    def test_warmup_can_recover(self):
        c=cap([(False,None),(True,np.zeros((4,4,3),np.uint8))])
        with patch('helpers.cv2.VideoCapture',return_value=c),patch('helpers.threading.Thread'):
            camera=CameraStream(params());self.assertTrue(camera.image_ready);camera.close()

    def test_tk_factory_rejects_background_thread_before_tk(self):
        errors=[]
        def background():
            try: inference_gui.create_inference_gui(NS())
            except RuntimeError as error:errors.append(str(error))
        with patch.object(inference_gui.tk,'Tk') as factory:
            t=threading.Thread(target=background);t.start();t.join()
        factory.assert_not_called();self.assertEqual(len(errors),1)

    def test_real_loop_pumps_and_destroys_gui_on_exit(self):
        b=run_one_frame(app,True)
        b.test_gui.update.assert_called()
        b.test_gui.destroy.assert_called_once()
        self.assertIsNone(b.test_params.gui)

    def test_camera_startup_error_never_creates_gui_or_model(self):
        p=NS(webui=False,backend=0,exit_ready=False,input_mode='camera')
        with patch.object(app.parameters,'Parameters',return_value=p),patch.object(app,'CameraStream',side_effect=CameraInputError('camera indisponivel')),patch.object(app.inference_gui,'create_inference_gui') as gui,patch.object(app.mp.solutions.pose,'Pose') as model,patch.object(app.messagebox,'showerror') as message:
            app.main()
        gui.assert_not_called();model.assert_not_called()
        message.assert_called_once()
        self.assertEqual(p.input_status,'camera indisponivel')
