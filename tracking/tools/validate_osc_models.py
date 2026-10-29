"""Integração positiva offline: imagens reais → MediaPipe → OSC → socket local.

Exige uma imagem de corpo inteiro e outra de mão detectável. Não testa VRChat,
movimento, calibração ou precisão. Nenhum download é feito por este programa.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import cv2
import mediapipe as mp
from scipy.spatial.transform import Rotation
from pythonosc.osc_packet import OscPacket

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from backends import VRChatOSCBackend
from independent_trackers import prepare_trackers
from osc_body import prepare_extra_trackers
from finger_tracking import FingerTracking


def read_rgb(path):
    image = cv2.imread(str(path))
    if image is None or not image.size:
        raise ValueError('Imagem inválida: ' + str(path))
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def receive(receiver):
    return {item.message.address: item.message.params
            for item in OscPacket(receiver.recv(65535)).messages}


def validate(pose_path, hand_path, left_half=False):
    pose_image, hand_image = read_rgb(pose_path), read_rgb(hand_path)
    if left_half:
        hand_image = hand_image[:, :hand_image.shape[1] // 2].copy()
    params = SimpleNamespace(global_rot_z=Rotation.identity(), global_rot_x=Rotation.identity(),
        global_rot_y=Rotation.identity(), posescale=1., hmd_to_neck_offset=[0,-.2,.1],
        min_visibility=.5, feet_rotation=False, use_hands=False, ignore_hip=False,
        backend=2, additional_smoothing=0., recalibrate=False, preview_skeleton=False)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1', 0)); receiver.settimeout(2)
        params.backend_ip, params.backend_port = receiver.getsockname()
        backend = VRChatOSCBackend()
        try:
            backend.connect(params)
            with mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1) as detector:
                detected = detector.process(pose_image)
                if not detected.pose_world_landmarks or not detected.pose_landmarks:
                    raise ValueError('Nenhuma pose detectada na imagem de teste')
                world, image = detected.pose_world_landmarks.landmark, detected.pose_landmarks.landmark
                frame = prepare_trackers(world, params, image_landmarks=image)
                extras = prepare_extra_trackers(world, image, params)
                if not all(frame.valid.values()) or len(extras) != 5:
                    raise ValueError('Imagem de teste deve produzir oito trackers válidos')
                if not backend.updatepose(params, frame.pose, frame.rotations, frame.hands, frame.valid, extras):
                    raise ValueError('Backend rejeitou os trackers')
                body_packet = receive(receiver)
            with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=2) as detector:
                fingers = FingerTracking(detector, backend.client)
                states = []
                for _ in range(3):
                    states.append(sorted(fingers.process(hand_image)))
                    hand_packet = receive(receiver)
                if not states[-1]:
                    raise ValueError('Nenhuma mão confirmada na imagem de teste')
                fingers.suspend()
                missing_packet = receive(receiver)
                if not all(value == [False] for value in missing_packet.values()):
                    raise ValueError('Perda de mão não gerou flags falsas')
        finally:
            backend.disconnect()
    return {'mediapipe': mp.__version__, 'opencv': cv2.__version__,
        'pose_image_sha256': hashlib.sha256(Path(pose_path).read_bytes()).hexdigest(),
        'hand_image_sha256': hashlib.sha256(Path(hand_path).read_bytes()).hexdigest(),
        'hand_left_half': left_half, 'body_addresses': len(body_packet),
        'hand_confirmation_states': states, 'hand_addresses': len(hand_packet),
        'missing_hand_flags': missing_packet, 'body_packet': body_packet, 'hand_packet': hand_packet,
        'vrchat_tested': False, 'note': 'Imagens estáticas distintas; não mede precisão, FPS ou sincronia corpo/mãos.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pose-image', required=True, type=Path)
    parser.add_argument('--hand-image', required=True, type=Path)
    parser.add_argument('--hand-left-half', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = validate(args.pose_image, args.hand_image, args.hand_left_half)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Integração MediaPipe/UDP concluída; resultado em ' + str(args.output))


if __name__ == '__main__':
    main()
