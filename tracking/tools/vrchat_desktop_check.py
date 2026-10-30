"""Testa pulo, menu ou ação de usar do VRChat por OSC, sem avatar customizado."""
import argparse
import math
import time
from pythonosc.udp_client import SimpleUDPClient


COMMANDS={
    'jump':('/input/Jump','Pulo enviado.'),
    'menu-left':('/input/QuickMenuToggleLeft','Alternância do menu esquerdo enviada.'),
    'menu-right':('/input/QuickMenuToggleRight','Alternância do menu direito enviada.'),
    'use-left':('/input/UseLeft','Ação de usar da mão esquerda enviada.'),
    'use-right':('/input/UseRight','Ação de usar da mão direita enviada.'),
}


def send_button(client, address, sleep=time.sleep):
    """Pulso explícito: libera antes/depois, inclusive em caso de interrupção."""
    if address not in {command[0] for command in COMMANDS.values()}:
        raise ValueError('Comando OSC não permitido')
    try:
        client.send_message(address,0)
        client.send_message(address,1)
        sleep(.15)
    finally:
        client.send_message(address,0)


def send_jump(client, sleep=time.sleep):
    # Mantém o comando anterior e os testes/integradores que o importam.
    send_button(client,'/input/Jump',sleep=sleep)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send',action='store_true',help='Enviar comando; sem esta opção só mostra a prévia.')
    parser.add_argument('--ip',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=9000)
    parser.add_argument('--command',choices=COMMANDS,default='jump',help='jump: pulo; menu-left/right: menu; use-left/right: ação de usar da mão em VR.')
    parser.add_argument('--delay',type=float,default=0.,help='Espera de 0 a 30 segundos para voltar à janela do VRChat.')
    args=parser.parse_args(argv)
    if not 1 <= args.port <= 65535: parser.error('Porta deve estar entre 1 e 65535')
    if not math.isfinite(args.delay) or not 0 <= args.delay <= 30:parser.error('Espera deve estar entre 0 e 30 segundos')
    address,confirmation=COMMANDS[args.command]
    if not args.send:
        print(f'Prévia: {address} 0 -> 1 -> 0. Espera: {args.delay:g} s. Use --send com VRChat aberto e OSC ligado.')
        return
    client=None
    try:
        if args.delay:
            print(f'Comando em {args.delay:g} s. Volte ao VRChat.',flush=True)
            time.sleep(args.delay)
        client=SimpleUDPClient(args.ip,args.port)
        send_button(client,address)
    except OSError as exc:
        parser.exit(2,f'Falha ao enviar OSC: {exc}\n')
    finally:
        if client is not None:client.close()
    print(confirmation+' UDP não confirma recepção; observe o VRChat.')


if __name__=='__main__': main()
