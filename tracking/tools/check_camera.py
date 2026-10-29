"""Diagnostica a captura sem Tk, MediaPipe, SteamVR ou envio OSC."""
import argparse
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from helpers import CameraStream,CameraInputError


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera',default='0')
    parser.add_argument('--seconds',type=float,default=15,help='Limite de observação em segundos (1 a 60).')
    parser.add_argument('--frames',type=int,default=10)
    args=parser.parse_args(argv)
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 60:parser.error('Tempo deve estar entre 1 e 60 segundos')
    if not 1 <= args.frames <= 100:parser.error('Quadros devem estar entre 1 e 100')
    params=SimpleNamespace(cameraid=args.camera,camera_settings=False,camera_height=0,camera_width=0,exit_ready=False)
    source=None
    try:
        source=CameraStream(params)
        deadline=time.perf_counter()+args.seconds
        frames=0
        while frames<args.frames and time.perf_counter()<deadline and not params.exit_ready:
            frame=source.read_latest()
            if frame is not None:
                frames+=1
                print(f'Quadro {frames}: {frame[0].shape[1]}x{frame[0].shape[0]}')
            else:time.sleep(.01)
        if params.exit_ready:
            raise CameraInputError(f'O driver interrompeu a captura após {frames} quadros.')
        if frames == 0:
            raise CameraInputError('Nenhum quadro foi recebido durante a observação.')
        if frames < args.frames:
            print(f'Captura parcial: {frames} quadros no limite de {args.seconds:g}s; fluxo lento ou bloqueado, sem erro de leitura reportado. Não é confirmação de desconexão.')
            raise SystemExit(2)
        print(f'Camera OK: {frames} quadros recebidos; recurso liberado ao terminar.')
    except CameraInputError as error:
        raise SystemExit(str(error))
    finally:
        if source is not None:source.close()


if __name__=='__main__': main()
