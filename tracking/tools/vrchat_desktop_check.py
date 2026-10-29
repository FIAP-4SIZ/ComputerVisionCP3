"""Envia um pulo de teste ao VRChat desktop, sem usar câmera ou avatar customizado."""
import argparse
import time
from pythonosc.udp_client import SimpleUDPClient


def send_jump(client, sleep=time.sleep):
    try:
        client.send_message('/input/Jump',0)
        client.send_message('/input/Jump',1)
        sleep(.15)
    finally:
        client.send_message('/input/Jump',0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send',action='store_true',help='Enviar comando; sem esta opção só mostra a prévia.')
    parser.add_argument('--ip',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=9000)
    args=parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('Porta deve estar entre 1 e 65535')
    if not args.send:
        print('Prévia: /input/Jump 0 → 1 → 0. Use --send com VRChat aberto e OSC ligado.')
        return
    send_jump(SimpleUDPClient(args.ip,args.port))
    print('Pulo enviado. UDP não confirma recepção; observe o personagem no VRChat.')


if __name__=='__main__': main()
