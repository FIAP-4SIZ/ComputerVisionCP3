"""Consulta driver/HMD; opcionalmente confirma FBT com pulso explícito."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
from steamvr_protocol import SteamVRHandsClient,DriverConnectionError


def watch_status(client,seconds,initial,clock=time.monotonic,sleep=time.sleep):
    """Amostra o receptor; não envia poses, confirmação ou invalidação."""
    if isinstance(seconds,bool) or not isinstance(seconds,(float,int)) or not math.isfinite(seconds) or not 0<seconds<=30:
        raise ValueError('Duração deve ser maior que zero e no máximo 30 segundos')
    start=clock();deadline=start+seconds
    summary={'samples':0,'observed_masks':[], 'samples_with_both_hands':0,
             'samples_with_valid_hmd':0,'cancelled':False}
    previous=None

    def record(status):
        nonlocal previous
        summary['samples']+=1
        mask=status['tracked_mask']
        if mask not in summary['observed_masks']:summary['observed_masks'].append(mask)
        summary['samples_with_both_hands']+=int(mask==3)
        summary['samples_with_valid_hmd']+=int(status['hmd_valid'])
        # Publica mudanças sem imprimir cinco linhas idênticas por segundo.
        if status!=previous:
            print(json.dumps({'elapsed_seconds':round(clock()-start,2),**status}),flush=True)
            previous=dict(status)

    record(initial)
    try:
        while True:
            remaining=deadline-clock()
            if remaining<=0:break
            sleep(min(.2,remaining))
            if clock()>=deadline:break
            record(client.status())
    except KeyboardInterrupt:
        summary['cancelled']=True
    summary['observed_masks'].sort()
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm',action='store_true',help='Somente após iniciar Calibrate FBT no VRChat em modo VR.')
    parser.add_argument('--delay',type=int,default=3)
    parser.add_argument('--head',action='store_true',help='Consultar matriz bruta do HMD para diagnóstico de altura/origem.')
    parser.add_argument('--watch',type=float,help='Observar o receptor por até 30 segundos, ex.: --watch 10. Sem enviar poses/cliques.')
    args=parser.parse_args(argv)
    if not 0<=args.delay<=10:parser.error('Atraso deve estar entre 0 e 10 segundos')
    if args.watch is not None:
        if not math.isfinite(args.watch) or not 0<args.watch<=30:parser.error('--watch deve ser maior que zero e no máximo 30 segundos')
        if args.confirm:parser.error('--watch não combina com --confirm')
    client=SteamVRHandsClient()
    try:
        status=client.status()
        print(json.dumps(status,indent=2))
        if not status['hmd_valid']:raise DriverConnectionError('HMD sem pose válida; confirme o modo VR e o driver null.')
        if args.head:print(json.dumps({'head_raw_matrix':client.head_pose()},indent=2))
        if args.watch is not None:
            print('Mostre as mãos à câmera mantendo a captura aberta. Ctrl+C encerra a observação.',flush=True)
            print(json.dumps({'watch_summary':watch_status(client,args.watch,status)},indent=2))
            print('Máscara 3 registra ambas as mãos válidas no receptor, não movimento ou bindings no VRChat.')
            return
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
