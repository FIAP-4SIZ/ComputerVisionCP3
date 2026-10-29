"""Recebe OSC local para inspecionar o remetente, sem ocupar a porta do VRChat."""
import argparse
import json
import math
import socket
import time
from pythonosc.osc_packet import OscPacket


def monitor(receiver, seconds=10., packets=0):
    if not math.isfinite(seconds) or not 0 < seconds <= 60 or not isinstance(packets, int) or packets < 0:
        raise ValueError('Use duração entre 0 e 60 segundos e limite de pacotes não negativo')
    start = time.monotonic()
    end = start + seconds
    result = {'packets': 0, 'malformed': 0, 'addresses': {}, 'last_values': {}, 'last_seen_seconds': {}}
    while time.monotonic() < end and (not packets or result['packets'] < packets):
        receiver.settimeout(max(.001, min(.25, end - time.monotonic())))
        try:
            data = receiver.recv(65535)
        except socket.timeout:
            continue
        result['packets'] += 1
        try:
            messages = OscPacket(data).messages
            for item in messages:
                message = item.message
                if any(not isinstance(v, (float, int, bool)) or not math.isfinite(v) for v in message.params):
                    raise ValueError('Esperados apenas números finitos ou flags')
                result['addresses'][message.address] = result['addresses'].get(message.address, 0) + 1
                result['last_values'][message.address] = message.params
                result['last_seen_seconds'][message.address] = round(time.monotonic() - start, 4)
        except Exception:
            result['malformed'] += 1
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9002)
    parser.add_argument('--seconds', type=float, default=10.)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or args.port == 9000:
        parser.error('Escolha uma porta válida diferente de 9000 (reservada aqui para VRChat)')
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60:
        parser.error('Duração deve ser maior que 0 e no máximo 60 segundos')
    print(f'Monitor local 127.0.0.1:{args.port}. Configure essa porta na aplicação durante o teste.', flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1', args.port))
        result = monitor(receiver, args.seconds)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    print('Este resultado confirma pacotes locais; não confirma animação ou recepção no VRChat.')
    return 0 if result['packets'] and not result['malformed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
