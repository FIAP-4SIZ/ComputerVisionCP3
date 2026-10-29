"""Trackers OSC adicionais. Cada orientação exige geometria observável própria."""
import numpy as np
from scipy.spatial.transform import Rotation
from body_observation import observe_body
from pose_validation import valid_alignment


EXTRA_IDS = {'chest': '4', 'right_knee': '5', 'left_knee': '6',
             'left_elbow': '7', 'right_elbow': '8'}


def prepare_extra_trackers(world, image, params):
    """Retorna posição e âncora no mesmo referencial do pipeline original.

    São estimativas monoculares, não profundidade medida. O peito é uma
    interpolação do tronco; a orientação de membros usa os eixos anatômicos.
    Nenhum punho ocupa um ID de OSC Trackers (a API não define esse papel).
    """
    if world is None or not hasattr(world, '__len__') or len(world) != 33 or not valid_alignment(params):
        return {}
    threshold = getattr(params, 'min_visibility', .5)
    visible = observe_body(image, threshold).visible
    points = np.full((33, 3), np.nan)
    for i in visible:
        try:
            if threshold <= float(world[i].visibility) <= 1:
                points[i] = [world[i].x, world[i].y, world[i].z]
        except (TypeError, ValueError, AttributeError):
            continue
    # Dados precisam ser representáveis como floats do protocolo OSC. Este
    # limite numérico também impede overflow nas normas/produtos vetoriais.
    points[np.any(np.abs(points) > np.finfo(np.float32).max, axis=1)] = np.nan
    # Exatamente a ordem de sinais/rotações usada em prepare_pose.
    points[:, :2] *= -1
    for rotation in (params.global_rot_z, params.global_rot_x, params.global_rot_y):
        points = rotation.apply(points)
    if not np.isfinite(points[[11, 12]]).all():
        return {}
    neck = (points[11] + points[12]) / 2
    across = points[11] - points[12]
    result = {}
    for name, indices in (('chest', (11, 12, 23, 24)),
                          ('right_knee', (23, 24, 26, 28)),
                          ('left_knee', (23, 24, 25, 27)),
                          ('left_elbow', (11, 12, 13, 15)),
                          ('right_elbow', (11, 12, 14, 16))):
        if not np.isfinite(points[list(indices)]).all():
            continue
        if name == 'chest':
            hips = (points[23] + points[24]) / 2
            position = .75 * neck + .25 * hips
            up = neck - hips
        elif name.endswith('knee'):
            hip, knee = (24, 26) if name == 'right_knee' else (23, 25)
            position, up = points[knee], points[hip] - points[knee]
        else:
            shoulder, elbow = (11, 13) if name == 'left_elbow' else (12, 14)
            position, up = points[elbow], points[shoulder] - points[elbow]
        # Gram-Schmidt: evita orientação indefinida/colinear, sem inventar eixo.
        length = np.linalg.norm(up)
        if length < 1e-6:
            continue
        y = up / length
        x = across - np.dot(across, y) * y
        length = np.linalg.norm(x)
        if length < 1e-6:
            continue
        x /= length
        quaternion = Rotation.from_matrix(np.column_stack((x, y, np.cross(x, y)))).as_quat()
        result[name] = (np.stack((position, neck)), quaternion)
    return result
