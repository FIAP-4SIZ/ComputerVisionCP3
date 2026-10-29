"""Compara o mesmo prefixo de vídeo, sem regravar a entrada ou transmitir para VR."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace

import cv2
import mediapipe as mp
import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from lighting import LightingSettings, apply_lighting, resize_for_pose
from video_source import VideoFileSource
from independent_trackers import prepare_trackers
from pose_validation import InvalidPose


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def image_metrics(image):
    y = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)[:, :, 0]
    return np.array([float(y.mean()), float(np.any(image == 0, axis=2).mean()),
                     float(np.any(image == 255, axis=2).mean())])


def compare_video(path, candidates=None, max_frames=120, max_size=640, pose_factory=None, progress=None):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Video inexistente')
    for value, zero_allowed in ((max_frames, True), (max_size, False)):
        if isinstance(value, bool) or not isinstance(value, int) or value < (0 if zero_allowed else 1):
            raise ValueError('Limite de quadros e tamanho invalidos')
    candidates = tuple(candidates) if candidates is not None else (
        LightingSettings(), LightingSettings('manual', 1.2, 20), LightingSettings('equalize'))
    if (not candidates or not all(isinstance(item, LightingSettings) for item in candidates)
            or candidates[0].mode != 'off'):
        raise ValueError('A primeira configuracao deve ser o original, seguida de ajustes validos')
    if pose_factory is None:
        pose_factory = lambda: mp.solutions.pose.Pose(model_complexity=1,
            smooth_landmarks=True, min_detection_confidence=.5, min_tracking_confidence=.5)
    original_hash = file_digest(path)
    params = SimpleNamespace(min_visibility=.5, feet_rotation=False, use_hands=False,
        preview_skeleton=False, ignore_hip=False, backend=0,
        global_rot_x=Rotation.identity(), global_rot_y=Rotation.from_euler('y', 180, degrees=True),
        global_rot_z=Rotation.identity())
    report = dict(input_sha256=original_hash, max_frames=max_frames, max_size=max_size,
        image_transform=dict(rotation_degrees=0, mirror=False),
        detector=dict(api='mp.solutions.pose', mediapipe=mp.__version__, model_complexity=1,
                      min_detection_confidence=.5, min_tracking_confidence=.5,
                      smooth_landmarks=True, static_image_mode=False, min_visibility=.5),
        note='Ensaio offline; visibilidade/deteccao nao medem precisao. FPS exclui hashes, estatisticas, abertura do modelo e GUI.',
        cases=[])
    baseline_fingerprint = None
    for case_index, settings in enumerate(candidates):
        source = VideoFileSource(path, pace=False)
        count = found = 0
        first_time = last_time = None
        ended = False
        timing = np.zeros(4)  # decode, PDI, pose, ciclo sem GUI/estatísticas/hashes
        original_stats = np.zeros(3)
        adjusted_stats = np.zeros(3)
        visibility_sum = visibility_count = 0
        tracker_counts = dict(hip=0, right_foot=0, left_foot=0)
        decoded = hashlib.sha256()
        try:
            with pose_factory() as detector:
                source.start()
                while max_frames == 0 or count < max_frames:
                    packet = source.read_latest()
                    if packet is None:
                        if source.state != 'completed':
                            raise RuntimeError('Leitura offline nao progrediu')
                        ended = True
                        break
                    original, decode_seconds, _ = packet
                    decoded.update(struct.pack('>Qd', source.index, source.timestamp_ms))
                    decoded.update(original.tobytes())
                    start = time.perf_counter()
                    original = resize_for_pose(original, max_size)
                    pre_start = time.perf_counter()
                    adjusted = apply_lighting(original, settings)
                    pre_seconds = time.perf_counter() - pre_start
                    rgb = cv2.cvtColor(adjusted, cv2.COLOR_BGR2RGB)
                    rgb.flags.writeable = False
                    pose_start = time.perf_counter()
                    result = detector.process(rgb)
                    pose_seconds = time.perf_counter() - pose_start
                    world = result.pose_world_landmarks
                    if world is not None:
                        try:
                            tracking = prepare_trackers(world.landmark, params)
                        except InvalidPose:
                            tracking = None
                        if tracking is not None:
                            for name, valid in tracking.valid.items():
                                tracker_counts[name] += bool(valid)
                    cycle_seconds = time.perf_counter() - start + decode_seconds
                    timing += [decode_seconds, pre_seconds, pose_seconds, cycle_seconds]
                    original_stats += image_metrics(original)
                    adjusted_stats += image_metrics(adjusted)
                    if world is not None:
                        found += 1
                        for index in (11, 12, 23, 24, 25, 26, 27, 28):
                            try:
                                value = float(world.landmark[index].visibility)
                            except (AttributeError, IndexError, TypeError, ValueError):
                                continue
                            if np.isfinite(value) and 0 <= value <= 1:
                                visibility_sum += value
                                visibility_count += 1
                    count += 1
                    if first_time is None:
                        first_time = source.timestamp_ms
                    last_time = source.timestamp_ms
                    if progress is not None and count % 60 == 0:
                        progress(case_index, count)
        finally:
            source.close()
        fingerprint = decoded.hexdigest()
        if baseline_fingerprint is not None and fingerprint != baseline_fingerprint:
            raise RuntimeError('Casos receberam quadros ou timestamps diferentes; comparacao invalida')
        baseline_fingerprint = fingerprint
        def stats(values):
            return dict(zip(('mean_luminance', 'fraction_any_channel_zero', 'fraction_any_channel_255'),
                            (values / count).tolist()))
        report['cases'].append(dict(settings=asdict(settings), frames=count, reached_eof=ended,
            decoded_frames_sha256=fingerprint, first_timestamp_ms=first_time, last_timestamp_ms=last_time,
            mean_decode_ms=timing[0] * 1000 / count, mean_preprocess_ms=timing[1] * 1000 / count,
            mean_pose_ms=timing[2] * 1000 / count, mean_cycle_ms=timing[3] * 1000 / count,
            approximate_offline_fps=count / timing[3] if timing[3] else 0,
            frames_with_pose=found, mean_relevant_visibility=visibility_sum / visibility_count if visibility_count else None,
            valid_tracker_frames=tracker_counts, original_image=stats(original_stats), adjusted_image=stats(adjusted_stats)))
    if file_digest(path) != original_hash:
        raise RuntimeError('Arquivo de entrada foi alterado antes de concluir o relatorio')
    report['input_unchanged'] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video')
    parser.add_argument('--frames', type=int, default=120, help='Prefixo; 0 processa todos os quadros')
    parser.add_argument('--max-size', type=int, default=640)
    parser.add_argument('--contrast', type=float, default=1.2)
    parser.add_argument('--brightness', type=float, default=20)
    parser.add_argument('--output', type=Path, help='JSON novo; nunca sobrescreve arquivo existente')
    args = parser.parse_args(argv)
    try:
        if args.output and (args.output.exists() or args.output.resolve() == Path(args.video).resolve()):
            raise ValueError('Escolha um caminho de saida novo, diferente da entrada')
        if args.output and not args.output.parent.is_dir():
            raise ValueError('Diretorio de saida inexistente')
        candidates = (LightingSettings(), LightingSettings('manual', args.contrast, args.brightness),
                      LightingSettings('equalize'))
        report = compare_video(args.video, candidates, args.frames, args.max_size,
                               progress=lambda case, frame: print(f'Caso {case + 1}/3: {frame} quadros', file=sys.stderr))
        content = json.dumps(report, indent=2, allow_nan=False)
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(content + '\n')
        else:
            print(content)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
