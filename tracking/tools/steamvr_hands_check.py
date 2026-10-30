"""Consulta driver/HMD; opcionalmente confirma FBT com pulso explícito."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from steamvr_protocol import SteamVRHandsClient,DriverConnectionError


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm',action='store_true',help='Somente após iniciar Calibrate FBT no VRChat em modo VR.')
    parser.add_argument('--delay',type=int,default=3)
    parser.add_argument('--head',action='store_true',help='Consultar matriz bruta do HMD para diagnóstico de altura/origem.')
    args=parser.parse_args(argv)
    if not 0<=args.delay<=10:parser.error('Atraso deve estar entre 0 e 10 segundos')
    client=SteamVRHandsClient()
    try:
        status=client.status()
        print(json.dumps(status,indent=2))
        if not status['hmd_valid']:raise DriverConnectionError('HMD sem pose válida; confirme o modo VR e o driver null.')
        if args.head:print(json.dumps({'head_raw_matrix':client.head_pose()},indent=2))
        if args.confirm:
            if not status['tracked_mask']:raise DriverConnectionError('Nenhuma mão válida. Inicie o MediaPipe e mostre mãos e punhos antes de confirmar.')
            print(f'Confirmação em {args.delay} s. Volte ao VRChat já em Calibrate FBT.',flush=True)
            for _ in range(args.delay):time.sleep(1)
            status=client.status()
            if not status['hmd_valid'] or not status['tracked_mask']:raise DriverConnectionError('Rastreamento perdido; confirmação cancelada.')
            client.confirm()
            print('Pulso enviado; observe a confirmação no VRChat. Requer binding de Interact/Use.')
        else:
            print('Driver respondeu; isso não confirma movimento do avatar ou bindings do VRChat.')
    except (OSError,DriverConnectionError) as exc:parser.exit(2,str(exc)+'\n')
    finally:client.close()


if __name__=='__main__':main()
