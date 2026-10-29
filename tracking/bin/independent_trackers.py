"""Validação e expiração local por tracker, sem reutilizar posições perdidas no envio."""

from dataclasses import dataclass
from types import SimpleNamespace
import math
import numpy as np

from helpers import mediapipeTo3dpose
from pose_validation import InvalidPose, prepare_pose
from body_observation import observe_body
from tracker_math import hip_rotation, leg_rotation, foot_rotation, hand_rotation


NAMES = ('hip', 'right_foot', 'left_foot', 'left_hand', 'right_hand')
JOINTS = dict(zip(NAMES, (6, 0, 5, 10, 15)))


def enabled_names(params):
    names = list(NAMES[:3])
    if getattr(params, 'ignore_hip', False):
        names.remove('hip')
    if getattr(params, 'use_hands', False) and getattr(params, 'backend', 1) != 2:
        names.extend(NAMES[3:])
    return tuple(names)


def tracker_mask(params, supplied=None):
    if supplied is not None:
        if not isinstance(supplied, dict) or set(supplied) - set(NAMES):
            raise ValueError('Máscara de trackers inválida')
        if any(not isinstance(v, (bool, np.bool_)) for v in supplied.values()):
            raise ValueError('A máscara deve conter booleanos')
    return {name: supplied.get(name, False) if supplied is not None else True
            for name in enabled_names(params)}


@dataclass
class TrackerFrame:
    pose: np.ndarray
    rotations: np.ndarray
    hands: object
    valid: dict
    reasons: dict
    calibration: object = None


_IMAGE_NOT_SUPPLIED = object()


def prepare_trackers(landmarks, params, image_landmarks=_IMAGE_NOT_SUPPLIED):
    # Compatibilidade para chamadas matemáticas antigas sem imagem. O laço real
    # sempre fornece os pontos normalizados, inclusive None quando não há pose.
    if image_landmarks is not _IMAGE_NOT_SUPPLIED:
        try:
            observation = observe_body(image_landmarks, getattr(params, 'min_visibility', .5))
            landmarks = [SimpleNamespace(x=p.x if i in observation.visible else math.nan,
                                         y=p.y, z=p.z,
                                         visibility=min(float(p.visibility), float(image_landmarks[i].visibility))
                                         if i in observation.visible else 0.)
                         for i, p in enumerate(landmarks)] if landmarks is not None else None
        except (AttributeError, TypeError, ValueError, IndexError) as exc:
            raise InvalidPose('Pontos de imagem ou espaciais inválidos') from exc
    names = enabled_names(params)
    valid = dict.fromkeys(names, False)
    reasons = {}
    try:
        # Caminho completo preserva as mesmas operações e a calibração existente.
        pose, calibration, rotations, hands = prepare_pose(landmarks, params)
        return TrackerFrame(pose, np.asarray(rotations), hands,
                            dict.fromkeys(names, True), {}, calibration)
    except InvalidPose as exc:
        if getattr(params, 'preview_skeleton', False):
            raise  # Preview usa 23 pontos; continua conservador, sem esconder sua falha.
        full_reason = str(exc)

    try:
        threshold = float(getattr(params, 'min_visibility', .5))
    except (ValueError, TypeError) as exc:
        raise InvalidPose('Limiar inválido') from exc
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise InvalidPose('Limiar inválido')
    if landmarks is None or not hasattr(landmarks, '__len__') or len(landmarks) != 33:
        raise InvalidPose(full_reason)

    coordinates = np.full((33, 3), np.nan)
    for index, point in enumerate(landmarks):
        try:
            coordinates[index] = [point.x, point.y, point.z]
        except (AttributeError, ValueError, TypeError):
            pass

    def require(indices):
        for index in indices:
            if not np.isfinite(coordinates[index]).all():
                raise InvalidPose(f'Landmark {index}: coordenadas invalidas')
            try:
                visibility = float(landmarks[index].visibility)
            except (AttributeError, ValueError, TypeError) as exc:
                raise InvalidPose(f'Landmark {index}: sem visibilidade') from exc
            if not math.isfinite(visibility) or not 0 <= visibility <= 1 or visibility < threshold:
                raise InvalidPose(f'Landmark {index}: visibilidade insuficiente')

    # Zero só preenche slots NÃO enviados. Cada tracker verifica suas dependências
    # antes de usar os pontos; nenhum placeholder é uma medição ou extrapolação.
    safe = np.nan_to_num(coordinates, nan=0., posinf=0., neginf=0.)
    points = [SimpleNamespace(x=x, y=y, z=z) for x, y, z in safe]
    pose = mediapipeTo3dpose(points)
    pose[:, :2] *= -1
    try:
        with np.errstate(divide='raise', invalid='raise', over='raise'):
            for index in range(len(pose)):
                pose[index] = params.global_rot_z.apply(pose[index])
                pose[index] = params.global_rot_x.apply(pose[index])
                pose[index] = params.global_rot_y.apply(pose[index])
    except (ValueError, FloatingPointError) as exc:
        raise InvalidPose('Transformacao invalida') from exc

    rotations = np.tile([0., 0., 0., 1.], (3, 1))
    hands = np.tile([0., 0., 0., 1.], (2, 1)) if getattr(params, 'use_hands', False) else None
    common = (11, 12, 23, 24)  # Pescoço, origem pélvica e alinhamento comum.
    for name in names:
        try:
            require(common)
            with np.errstate(divide='raise', invalid='raise', over='raise'):
                if name == 'hip':
                    quaternion = hip_rotation(pose)
                elif name.endswith('foot'):
                    right = name == 'right_foot'
                    require((26, 28) if right else (25, 27))
                    if params.feet_rotation:
                        require((30, 32) if right else (29, 31))
                        quaternion = foot_rotation(pose, right)
                    else:
                        if not right:
                            y, w = pose[4] - pose[5], pose[3] - pose[5]
                            if np.sqrt(sum(np.cross(w, y)**2)) < 1e-6:
                                require((28,))  # Fallback original usa o outro tornozelo.
                        quaternion = leg_rotation(pose, right)
                else:
                    right = name == 'right_hand'
                    require((16, 18, 20) if right else (15, 17, 19))
                    quaternion = hand_rotation(pose, right)
            if not np.isfinite(quaternion).all() or not np.isclose(np.linalg.norm(quaternion), 1):
                raise InvalidPose('Orientacao invalida')
            if name in NAMES[:3]:
                rotations[NAMES.index(name)] = quaternion
            else:
                hands[NAMES.index(name) - 3] = quaternion
            valid[name] = True
        except (InvalidPose, ValueError, FloatingPointError) as exc:
            reasons[name] = str(exc)
    # Calibração automática continua exigindo pose completa, nunca usa placeholders.
    return TrackerFrame(pose, rotations, hands, valid, reasons)


class TrackerLifecycle:
    def __init__(self, names):
        self.names = tuple(names)
        if set(self.names) - set(NAMES) or len(set(self.names)) != len(self.names):
            raise ValueError('Nomes de trackers invalidos')
        self.reset()

    def reset(self):
        self.last_seen = dict.fromkeys(self.names, None)
        self.states = dict.fromkeys(self.names, 'unavailable')
        self.timestamp = None

    def invalidate(self):
        self.reset()
        self.states = dict.fromkeys(self.names, 'expired')
        return set(self.names)

    def update(self, valid, timestamp, timeout=0.):
        if not isinstance(valid, dict) or set(valid) - set(self.names):
            raise ValueError('Estado de trackers invalido')
        if any(not isinstance(v, (bool, np.bool_)) for v in valid.values()):
            raise ValueError('Estado de tracker deve ser booleano')
        try:
            timestamp, timeout = float(timestamp), float(timeout)
        except (ValueError, TypeError) as exc:
            raise ValueError('Tempo de tracker invalido') from exc
        if not math.isfinite(timestamp) or timestamp < 0 or not math.isfinite(timeout) or timeout < 0:
            raise ValueError('Tempo de tracker invalido')
        if self.timestamp is not None and timestamp < self.timestamp:
            raise ValueError('Timestamp de tracker regressivo; reinicie a analise')
        self.timestamp = timestamp
        expired = set()
        for name in self.names:
            previous = self.last_seen[name]
            age = timestamp - previous if previous is not None else 0.
            # 0.3 - 0.1 pode ser 0.19999999999999998; não atrasar um quadro por isso.
            overdue = previous is not None and timeout > 0 and (
                age >= timeout or math.isclose(age, timeout, rel_tol=0, abs_tol=1e-9))
            if overdue or (previous is not None and not valid.get(name, False) and timeout == 0):
                expired.add(name)
                self.last_seen[name] = None
                self.states[name] = 'expired'
            if valid.get(name, False):
                self.last_seen[name] = timestamp
                self.states[name] = 'active'
            elif self.last_seen[name] is not None:
                self.states[name] = 'missing'
        return expired

    def summary(self):
        labels = dict(zip(NAMES, ('Q', 'PD', 'PE', 'ME', 'MD')))
        states = {'active': 'ok', 'missing': 'ausente', 'expired': 'expirado', 'unavailable': 'sem dados'}
        return ' | '.join(f'{labels[name]}:{states[state]}' for name, state in self.states.items())
