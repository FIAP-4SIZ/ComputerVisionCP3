"""Contrato configurável de parâmetros de avatar; não cria animações no VRChat."""
import json
import math
from pathlib import Path

SIDES = ('Left', 'Right')
FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Little')


class OSCProfileError(ValueError):
    pass


def default_profile():
    return {'channels': [dict(side=side, finger=finger, source=source,
                              address=f'/avatar/parameters/MP_{side}_{finger}{suffix}')
                         for side in SIDES for finger in FINGERS
                         for source, suffix in (('curl', ''), ('spread', '_Spread'))],
            'tracked': {side: f'/avatar/parameters/MP_{side}_Tracked' for side in SIDES}}


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) - {'channels', 'tracked', 'enabled'}:
        raise ValueError('Perfil OSC de mãos inválido')
    channels = profile.get('channels')
    if not isinstance(channels, list) or not 1 <= len(channels) <= 20:
        raise ValueError('Perfil deve conter entre 1 e 20 canais')
    used = set()

    def address(value):
        if (not isinstance(value, str) or not value.startswith('/avatar/parameters/')
                or not value.removeprefix('/avatar/parameters/')
                or any(ord(c) <= 32 or c in '#*,?[]{}' for c in value)
                or '/' in value.removeprefix('/avatar/parameters/')
                or len(value) > 256 or value in used):
            raise ValueError('Endereço OSC inválido ou duplicado')
        used.add(value)
        return value

    result = {'channels': [], 'tracked': {}}
    for channel in channels:
        if (not isinstance(channel, dict)
                or set(channel) - {'side', 'finger', 'source', 'address', 'scale', 'offset', 'min', 'max'}
                or channel.get('side') not in SIDES or channel.get('finger') not in FINGERS
                or channel.get('source') not in ('curl', 'spread')):
            raise ValueError('Canal OSC inválido')
        item = dict(channel)
        address(item.get('address'))
        for name, default in (('scale', 1.), ('offset', 0.), ('min', 0.), ('max', 1.)):
            value = item.get(name, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) > 1e6 or not math.isfinite(value):
                raise ValueError('Escala/limites OSC inválidos')
            item[name] = float(value)
        if item['min'] >= item['max']:
            raise ValueError('Limites OSC invertidos')
        result['channels'].append(item)
    tracked = profile.get('tracked', {})
    if not isinstance(tracked, dict) or set(tracked) - set(SIDES):
        raise ValueError('Flags de rastreamento inválidas')
    for side, path in tracked.items():
        result['tracked'][side] = address(path)
    if 'enabled' in profile:
        result['enabled'] = address(profile['enabled'])
    return result


def load_profile(path=''):
    if not path:
        return validate_profile(default_profile())
    try:
        path = Path(path)
        if path.stat().st_size > 131072:
            raise ValueError('Perfil OSC muito grande (máximo 128 KiB)')
        return validate_profile(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError) as exc:
        raise OSCProfileError('Não foi possível carregar o perfil OSC das mãos: ' + str(exc)) from exc


def hand_messages(profile, frames):
    """Somente amostras válidas; mão ausente envia flag, não coordenada neutra."""
    messages = [(path, side in frames) for side, path in profile['tracked'].items()]
    if 'enabled' in profile:
        messages.append((profile['enabled'], bool(frames)))
    for channel in profile['channels']:
        frame = frames.get(channel['side'])
        if frame is None:
            continue
        values = frame.curls if channel['source'] == 'curl' else frame.spreads
        if values is None or channel['finger'] not in values:
            continue
        value = values[channel['finger']]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1 or not math.isfinite(value):
            continue
        value = value * channel['scale'] + channel['offset']
        messages.append((channel['address'], float(max(channel['min'], min(channel['max'], value)))))
    return messages
