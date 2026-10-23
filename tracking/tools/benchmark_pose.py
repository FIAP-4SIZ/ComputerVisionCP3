"""Benchmark offline da inferência; não mede câmera física, GUI ou backend VR.

python tools/benchmark_pose.py caminho/video.mp4 --frames 60
"""

import argparse
import json
import sys
import time
from pathlib import Path
from statistics import mean

import cv2
import mediapipe as mp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
from frame_metrics import FrameMetrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video')
    parser.add_argument('--frames', type=int, default=60)
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error('--frames deve ser positivo')

    frames, decode_times = [], []
    capture = cv2.VideoCapture(args.video)
    try:
        while len(frames) < args.frames:
            start = time.perf_counter()
            ok, frame = capture.read()
            elapsed = time.perf_counter() - start
            if not ok:
                break
            # Mesmo limite e mesma interpolação da aplicação original.
            if max(frame.shape) > 640:
                ratio = max(frame.shape) / 640
                frame = cv2.resize(frame, (int(frame.shape[1] / ratio), int(frame.shape[0] / ratio)))
            frames.append(frame)
            decode_times.append(elapsed)
    finally:
        capture.release()
    if not frames:
        parser.error('Nenhum quadro lido: verifique o caminho e o codec')

    output = {'frames': len(frames), 'decode_mean_ms': mean(decode_times) * 1000,
              'note': 'Offline, sem GUI/backend; vídeo é decodificado antes das duas execuções.'}
    # Mesmos pixels, parâmetros, aquecimento e detector novo em cada execução.
    # A diferença experimental é somente adicionar/resumir as métricas.
    for measured in (False, True):
        durations, detected = [], 0
        metrics = FrameMetrics()
        with mp.solutions.pose.Pose(model_complexity=1, smooth_landmarks=True,
                                    min_detection_confidence=.5,
                                    min_tracking_confidence=.5) as detector:
            for _ in range(5):
                detector.process(cv2.cvtColor(frames[0], cv2.COLOR_BGR2RGB))
            pose_times = []
            for frame in frames:
                start = time.perf_counter()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False
                pose_start = time.perf_counter()
                result = detector.process(rgb)
                elapsed = time.perf_counter() - pose_start
                pose_times.append(elapsed)
                detected += result.pose_world_landmarks is not None
                if measured:
                    metrics.add(capture=0, age=0, pose=elapsed, trackers=0,
                                cycle=time.perf_counter() - start)
                    metrics.summary()
                durations.append(time.perf_counter() - start)
        output['with_metrics' if measured else 'without_metrics'] = {
            'pose_mean_ms': mean(pose_times) * 1000,
            'offline_cycle_mean_ms': mean(durations) * 1000,
            'offline_fps': len(durations) / sum(durations),
            'frames_with_pose': detected,
        }
    # Isola o custo das métricas da variação do tempo da rede neural entre execuções.
    start = time.perf_counter()
    for _ in range(10000):
        metrics.add(capture=.01, age=.001, pose=.02, trackers=0, cycle=.04)
        metrics.summary()
    output['metrics_add_summary_mean_us'] = (time.perf_counter() - start) * 1e6 / 10000
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
