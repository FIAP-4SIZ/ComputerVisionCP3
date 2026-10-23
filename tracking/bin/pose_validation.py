"""Validação simples dos landmarks antes de produzir trackers para qualquer entrada."""

import math
import numpy as np
from helpers import mediapipeTo3dpose, get_rot, get_rot_mediapipe, get_rot_hands


class InvalidPose(ValueError):
    pass


def prepare_pose(landmarks, params):
    """Retorna posição transformada, pose para calibração, rotações e mãos.

    Uma pose rejeitada não gera novas coordenadas: não inventamos profundidade
    nem interpolamos articulações ocultas. Visibility não é medida de precisão.
    """
    threshold = getattr(params, 'min_visibility', .5)
    try:
        threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise InvalidPose('Limiar de visibilidade inválido') from exc
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise InvalidPose('Limiar de visibilidade deve estar entre 0 e 1')
    if landmarks is None or not hasattr(landmarks, '__len__') or len(landmarks) != 33:
        raise InvalidPose('Esperados 33 landmarks')
    try:
        coordinates = np.array([[p.x, p.y, p.z] for p in landmarks], dtype=float)
    except (AttributeError, TypeError, ValueError) as exc:
        raise InvalidPose('Landmarks sem coordenadas válidas') from exc
    if coordinates.shape != (33, 3) or not np.isfinite(coordinates).all():
        raise InvalidPose('Coordenadas não finitas')

    required = {11, 12, 23, 24, 25, 26, 27, 28}
    if params.feet_rotation:
        required.update((29, 30, 31, 32))
    if params.use_hands:
        required.update((15, 16, 17, 18, 19, 20))
    if getattr(params, 'preview_skeleton', False):
        required.update((0, 9, 10, 13, 14, 15, 16, 17, 18, 19, 20, 29, 30, 31, 32))
    for index in sorted(required):
        visibility = getattr(landmarks[index], 'visibility', None)
        try:
            visibility = float(visibility)
        except (ValueError, TypeError) as exc:
            raise InvalidPose(f'Landmark {index} sem visibilidade válida') from exc
        if not math.isfinite(visibility) or not 0 <= visibility <= 1:
            raise InvalidPose(f'Landmark {index} com visibilidade insuficiente ou inválida')
        if visibility < threshold:
            raise InvalidPose(f'Landmark {index}: vis {visibility:.2f} < limiar {threshold:.2f}')

    try:
        with np.errstate(divide='raise', invalid='raise', over='raise'):
            pose = mediapipeTo3dpose(landmarks)
            pose[:, 0] *= -1
            pose[:, 1] *= -1
            calibration = pose.copy()
            for index in range(len(pose)):
                pose[index] = params.global_rot_z.apply(pose[index])
                pose[index] = params.global_rot_x.apply(pose[index])
                pose[index] = params.global_rot_y.apply(pose[index])
            rotations = get_rot_mediapipe(pose) if params.feet_rotation else get_rot(pose)
            hands = get_rot_hands(pose) if params.use_hands else None
    except (ValueError, FloatingPointError) as exc:
        raise InvalidPose('Geometria degenerada: não é possível calcular orientação') from exc
    if not valid_tracker_data(pose, rotations, hands):
        raise InvalidPose('Posição ou orientação resultante inválida')
    return pose, calibration, rotations, hands


def valid_tracker_data(pose, rotations, hands=None):
    try:
        pose = np.asarray(pose, dtype=float)
        if pose.shape != (29, 3) or not np.isfinite(pose).all():
            return False
        rotations = np.asarray(rotations, dtype=float)
        if rotations.shape != (3, 4) or not np.isfinite(rotations).all():
            return False
        if not np.allclose(np.linalg.norm(rotations, axis=1), 1, atol=1e-5):
            return False
        if hands is not None:
            hands = np.asarray(hands, dtype=float)
            if hands.shape != (2, 4) or not np.isfinite(hands).all():
                return False
            if not np.allclose(np.linalg.norm(hands, axis=1), 1, atol=1e-5):
                return False
        return True
    except (ValueError, TypeError):
        return False


def valid_alignment(params):
    try:
        scale = float(params.posescale)
        offset = np.asarray(params.hmd_to_neck_offset, dtype=float)
        return (math.isfinite(scale) and scale > 0 and offset.shape == (3,)
                and bool(np.isfinite(offset).all()))
    except (AttributeError, TypeError, ValueError):
        return False
