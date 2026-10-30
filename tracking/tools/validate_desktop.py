"""Smoke de widgets Tk e janela OpenCV reais; exige desktop ou display virtual.
Não testa webcam, driver SteamVR ou headset. Falhas retornam código não zero.
Execute como processo: python tools/validate_desktop.py
"""
import json
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import init_gui
from parameters import Parameters
from inference_gui import InferenceWindow
from lighting import DEFAULT_LIGHTING
import cv2
import numpy as np
from osc_hands import default_profile


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


def button(root, label):
    return next(w for w in widgets(root) if isinstance(w, (tk.Button, tk.Radiobutton)) and w.cget('text') == label)


@contextmanager
def isolated_settings():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        try:
            os.chdir(directory)
            yield
        finally:
            os.chdir(previous)


def main():
    with isolated_settings():
        profile_path = Path.cwd() / 'perfil.json'
        profile_path.write_text(json.dumps(default_profile()), encoding='utf-8')
        original_loop = tk.Tk.mainloop
        def automated_loop(root, *args, **kwargs):
            root.after(5000, root.quit)
            def save():
                button(root, 'SteamVR mãos + OSC').invoke()
                finger_toggle = next(w for w in widgets(root) if isinstance(w, tk.Checkbutton)
                                     and w.cget('text').startswith('Rastrear dedos'))
                assert finger_toggle.cget('state') == 'disabled'
                full_body = next(w for w in widgets(root) if isinstance(w, tk.Checkbutton)
                                 and w.cget('text').startswith('OSC: incluir'))
                full_body.invoke()
                with patch.object(init_gui.filedialog, 'askopenfilename', return_value=str(profile_path)):
                    button(root, 'Selecionar perfil de mãos...').invoke()
                button(root, 'Salvar e continuar').invoke()
            root.after(100, save)
            original_loop(root, *args, **kwargs)
        with patch.object(tk.Tk, 'mainloop', automated_loop):
            initial = init_gui.getparams()
        assert initial['backend'] == 4
        assert initial['track_fingers'] is True
        assert initial['osc_full_body'] is True
        assert initial['osc_hand_profile'] == str(profile_path)
        initial['input_mode'] = 'video'
        initial['video_path'] = 'sample.avi'
        with patch('parameters.getparams', return_value=initial), patch.object(Parameters, 'load_params'):
            params = Parameters()
        assert params.osc_full_body is True
        assert params.osc_hand_profile == str(profile_path)
        root = tk.Tk()
        try:
            window = InferenceWindow(root, params)
            window.pack(side="top", fill="both", expand=True)
            root.update()
            button(root,'Confirmar FBT no VRChat em 3 segundos').invoke()
            assert params.request_fbt_confirmation is True
            params.request_fbt_confirmation=False
            pause = button(root, 'Pausar / retomar rastreamento')
            pause.invoke()
            assert params.paused
            button(root, 'Iniciar / retomar vídeo').invoke()
            assert not params.paused
            button(root, 'Reiniciar vídeo').invoke()
            assert params.restart_input
            button(root, 'Cancelar vídeo').invoke()
            assert params.cancel_input
            combo = next(w for w in widgets(root) if w.winfo_class() == 'TCombobox')
            combo.set('Brilho e contraste')
            entries = [w for w in widgets(combo.master.master) if w.winfo_class() == 'Entry']
            for entry, value in zip(entries, ('1.2', '20')):
                entry.delete(0, 'end')
                entry.insert(0, value)
            button(root, 'Aplicar iluminação').invoke()
            assert params.lighting.mode == 'manual'
            assert params.lighting.contrast == 1.2 and params.lighting.brightness == 20
            entries[0].delete(0, 'end')
            entries[0].insert(0, 'nan')
            button(root, 'Aplicar iluminação').invoke()
            assert params.lighting.contrast == 1.2
            button(root, 'Restaurar original').invoke()
            assert params.lighting == DEFAULT_LIGHTING
            root.update()
            result = dict(real_widgets=True, controls='passed',
                required_size=[root.winfo_reqwidth(), root.winfo_reqheight()],
                screen=[root.winfo_screenwidth(), root.winfo_screenheight()])
            # Valida acesso ao último controle numa janela pequena de verdade.
            root.geometry('640x480')
            root.update()
            window.viewport.canvas.yview_moveto(1.)
            root.update()
            exit_button = button(root, 'Sair')
            assert exit_button.winfo_rooty() >= root.winfo_rooty()
            assert exit_button.winfo_rooty() + exit_button.winfo_height() <= root.winfo_rooty() + root.winfo_height()
            window.viewport.canvas.yview_moveto(0.)
            window.viewport._wheel(type('Wheel', (), {'delta': -120})())
            root.update()
            assert window.viewport.canvas.yview()[0] > 0
            result['small_window_scroll'] = 'passed'
            result['fits_screen'] = all(a <= b for a, b in zip(result['required_size'], result['screen']))
        finally:
            root.destroy()

    original = np.full((240, 320, 3), 80, np.uint8)
    from lighting import LightingSettings, apply_lighting, comparison_view
    settings = LightingSettings('manual', 1.2, 20, True)
    view = comparison_view(original, apply_lighting(original, settings), settings)
    try:
        cv2.namedWindow('Validação da interface')
        cv2.imshow('Validação da interface', view)
        cv2.waitKey(100)
        assert cv2.getWindowProperty('Validação da interface', cv2.WND_PROP_VISIBLE) >= 1
        result['opencv_window'] = 'passed'
    finally:
        cv2.destroyAllWindows()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
