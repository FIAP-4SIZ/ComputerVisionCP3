"""Orientações originais, separadas para uma perna inválida não bloquear as demais."""

import numpy as np
from scipy.spatial.transform import Rotation as R


def frame_rotation(forward, back, up, hand=False):
    x = forward - back
    w = up - back
    z = np.cross(x, w)
    y = np.cross(z, x)
    x = x / np.sqrt(sum(x**2))
    y = y / np.sqrt(sum(y**2))
    z = z / np.sqrt(sum(z**2))
    matrix = np.vstack((z, y, -x) if hand else (x, y, z)).T
    return R.from_matrix(matrix).as_quat()


def hip_rotation(pose):
    return frame_rotation(pose[3], pose[2], pose[16])


def leg_rotation(pose, right):
    # Mantém os mesmos índices, produtos vetoriais e fallback do código original.
    knee, ankle, hip = (1, 0, 2) if right else (4, 5, 3)
    y = pose[knee] - pose[ankle]
    w = pose[hip] - pose[ankle]
    z = np.cross(w, y)
    if np.sqrt(sum(z**2)) < 1e-6:
        w = pose[3] - pose[0] if right else pose[2] - pose[0]
        z = np.cross(w, y)
    x = np.cross(y, z)
    x = x / np.sqrt(sum(x**2))
    y = y / np.sqrt(sum(y**2))
    z = z / np.sqrt(sum(z**2))
    return R.from_matrix(np.vstack((x, y, z)).T).as_quat()


def foot_rotation(pose, right):
    forward, back, up = (20, 21, 22) if right else (17, 18, 19)
    return frame_rotation(pose[forward], pose[back], pose[up])


def hand_rotation(pose, right):
    forward, back, up = (26, 27, 28) if right else (23, 24, 25)
    return frame_rotation(pose[forward], pose[back], pose[up], hand=True)
