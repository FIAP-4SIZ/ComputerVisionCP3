"""Diagnostica a captura sem Tk, MediaPipe, SteamVR ou envio OSC."""
import argparse
from pathlib import Path
import sys
import time
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from helpers import CameraStream,CameraInputError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera',default='0')
    args=parser.parse_args()
    params=SimpleNamespace(cameraid=args.camera,camera_settings=False,camera_height=0,camera_width=0,exit_ready=False)
    source=None
    try:
        source=CameraStream(params)
        deadline=time.perf_counter()+5
        frames=0
        while frames<10 and time.perf_counter()<deadline and not params.exit_ready:
            frame=source.read_latest()
            if frame is not None:
                frames+=1
                print(f'Quadro {frames}: {frame[0].shape[1]}x{frame[0].shape[0]}')
            else:time.sleep(.01)
        if frames<10: raise CameraInputError('Captura interrompida ou sem quadros suficientes.')
        print('Camera OK: 10 quadros recebidos; recurso liberado ao terminar.')
    except CameraInputError as error:
        raise SystemExit(str(error))
    finally:
        if source is not None:source.close()


if __name__=='__main__': main()
