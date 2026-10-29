import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch, mock_open

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import init_gui
import inference_gui
import mediapipepose as app
from video_source import VideoInputError
from helpers import CameraStream


class Var:
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class InputControlTests(unittest.TestCase):
    def test_file_picker_selects_video_and_analysis_backend(self):
        buttons = {}
        root = Mock()
        def button(*args, **kwargs):
            buttons[kwargs['text']] = kwargs['command']
            return Mock()
        def entry(*args, **kwargs):
            result = Mock()
            value = ['']
            result.insert.side_effect = lambda index, text: value.__setitem__(0, text)
            result.get.side_effect = lambda: value[0]
            return result
        root.mainloop.side_effect = lambda: buttons['Selecionar vídeo...']()
        with ExitStack() as stack:
            for name in ('Label', 'Frame', 'Radiobutton', 'Checkbutton'):
                stack.enter_context(patch.object(init_gui.tk, name, return_value=Mock()))
            stack.enter_context(patch.object(init_gui.tk, 'Tk', return_value=root))
            stack.enter_context(patch.object(init_gui.tk, 'IntVar', Var))
            stack.enter_context(patch.object(init_gui.tk, 'StringVar', Var))
            stack.enter_context(patch.object(init_gui.tk, 'Entry', side_effect=entry))
            stack.enter_context(patch.object(init_gui.tk, 'Button', side_effect=button))
            stack.enter_context(patch('init_gui.filedialog.askopenfilename', return_value='/tmp/sample.avi'))
            stack.enter_context(patch('builtins.open', mock_open()))
            stack.enter_context(patch('init_gui.pickle.load', return_value={}))
            save = stack.enter_context(patch('init_gui.pickle.dump'))
            result = init_gui.getparams()
        self.assertEqual(result['input_mode'], 'video')
        self.assertEqual(result['video_path'], '/tmp/sample.avi')
        self.assertEqual(result['backend'], 0)
        self.assertFalse(result['track_fingers'])
        self.assertEqual(save.call_args.args[0]['video_path'], '/tmp/sample.avi')

    def test_controls_signal_pause_resume_restart_and_cancel(self):
        window = Mock()
        window.params = SimpleNamespace(paused=False, restart_input=False, cancel_input=False,
                                         input_status='paused')
        inference_gui.InferenceWindow.pause_tracking(window)
        self.assertTrue(window.params.paused)
        inference_gui.InferenceWindow.resume_video(window)
        self.assertFalse(window.params.paused)
        inference_gui.InferenceWindow.restart_video(window)
        self.assertTrue(window.params.restart_input)
        inference_gui.InferenceWindow.cancel_video(window)
        self.assertTrue(window.params.cancel_input)
        inference_gui.InferenceWindow.refresh_input_status(window)
        window.input_status.set.assert_called_once_with('paused')
        window.root.after.assert_called_once_with(100, window.refresh_input_status)

    def test_open_error_reports_message_and_disconnects_backend(self):
        params = SimpleNamespace(webui=False, backend=0, exit_ready=False,
                                 input_mode='video', video_path='/bad.avi')
        backend = Mock()
        with patch.object(app.parameters, 'Parameters', return_value=params), \
             patch.object(app, 'DummyBackend', return_value=backend), \
             patch.object(app, 'VideoFileSource', side_effect=VideoInputError('corrupt')), \
             patch.object(app.messagebox, 'showerror') as report, \
             patch.object(app.cv2, 'destroyAllWindows'):
            app.main()
        report.assert_called_once()
        self.assertEqual(params.input_status, 'corrupt')
        backend.disconnect.assert_called_once()

    def test_camera_close_is_idempotent(self):
        camera = CameraStream.__new__(CameraStream)
        camera.thread = Mock()
        camera.thread.is_alive.return_value = False
        camera.cap = Mock()
        camera.close()
        camera.close()
        self.assertTrue(camera.stopped)
        camera.cap.release.assert_called_once()
        camera.thread.join.assert_called_once_with(timeout=1)


if __name__ == '__main__':
    unittest.main()
