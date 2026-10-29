"""Médias de uma janela curta, sem dependências além do Python."""

from collections import deque


class FrameMetrics:
    def __init__(self, window=60):
        self.samples = deque(maxlen=window)

    def add(self, *, capture, age, pose, trackers, cycle):
        # Todos os tempos entram em segundos, medidos com perf_counter().
        self.samples.append((capture, age, pose, trackers, cycle))

    def summary(self):
        if not self.samples:
            return 'Aguardando primeiro quadro completo'
        count = len(self.samples)
        capture, age, pose, trackers, cycle = (
            sum(values) / count for values in zip(*self.samples)
        )
        fps = 1 / cycle if cycle > 0 else 0.0
        return (f'FPS:{fps:.1f} | ciclo:{cycle * 1000:.1f}ms | '
                f'captura:{capture * 1000:.1f}ms | idade:{age * 1000:.1f}ms | '
                f'pose:{pose * 1000:.1f}ms | rastreadores:{trackers * 1000:.1f}ms')
