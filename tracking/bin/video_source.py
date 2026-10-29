"""Leitura sequencial e reprodução temporal de arquivo, com memória limitada."""

import math
import time
from pathlib import Path

import cv2


class VideoInputError(ValueError):
    pass


class VideoFileSource:
    def __init__(self, path, clock=time.perf_counter, pace=True):
        self.path = Path(path)
        if not self.path.is_file():
            raise VideoInputError('Selecione um arquivo de vídeo existente.')
        if self.path.suffix.lower() not in {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.mpg', '.mpeg'}:
            raise VideoInputError('Formato de arquivo não suportado.')
        self.clock = clock
        if not isinstance(pace, bool):
            raise VideoInputError('Agendamento deve ser booleano')
        self.pace = pace
        self.cap = None
        self.state = 'ready'
        self.error = ''
        self._open()

    def _open(self):
        self.cap = cv2.VideoCapture(str(self.path))
        try:
            if not self.cap.isOpened():
                raise VideoInputError('Não foi possível decodificar o vídeo; verifique arquivo e codec.')
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(self.fps) or self.fps <= 0:
                raise VideoInputError('Vídeo sem FPS válido: não é possível preservar sua escala de tempo.')
            count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.total = int(count) if math.isfinite(count) and count > 0 else None
            self.index = -1
            self.timestamp_ms = 0.0
            self.timestamp_estimated = False
            self._decoded = 0
            self._previous_timestamp = -1.0
            self._pending = self._decode()
            if self._pending is None:
                raise VideoInputError('Vídeo sem quadros válidos.')
            self.state = 'ready'
            self.error = ''
        except Exception as exc:
            self.close()
            if isinstance(exc, VideoInputError):
                raise
            raise VideoInputError('Falha ao abrir vídeo: ' + str(exc)) from exc

    def _decode(self):
        start = self.clock()
        ok, image = self.cap.read()
        captured_at = self.clock()
        if not ok:
            if self._decoded and self.total and self._decoded < self.total:
                raise VideoInputError('Vídeo interrompido antes do número de quadros informado pelo arquivo.')
            return None
        if image is None or image.size == 0 or image.ndim != 3 or image.shape[2] != 3:
            raise VideoInputError('Quadro inválido ou corrompido.')
        timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        # Alguns codecs devolvem zero sempre. O índice/FPS fornece uma estimativa explícita.
        estimated = not math.isfinite(timestamp) or timestamp < 0 or timestamp <= self._previous_timestamp
        if estimated:
            timestamp = max(self._decoded * 1000 / self.fps,
                            self._previous_timestamp + 1000 / self.fps)
        self._previous_timestamp = timestamp
        packet = (image, captured_at - start, captured_at, timestamp, self._decoded, estimated)
        self._decoded += 1
        return packet

    def start(self):
        if self.state == 'ready':
            self._anchor = self.clock() - self._pending[3] / 1000
            self.state = 'running'
        elif self.state == 'paused':
            self._anchor += self.clock() - self._paused_at
            self.state = 'running'

    def pause(self):
        if self.state == 'running':
            self._paused_at = self.clock()
            self.state = 'paused'

    def read_latest(self):
        """Mesmo contrato da câmera, mas nunca descarta quadros do arquivo."""
        if self.state != 'running':
            return None
        try:
            if self._pending is None:
                self._pending = self._decode()
            if self._pending is None:
                self.state = 'completed'
                self.close()
                return None
            if self.pace and self.clock() < self._anchor + self._pending[3] / 1000:
                return None
            image, duration, captured_at, timestamp, index, estimated = self._pending
            self._pending = None
            self.index, self.timestamp_ms = index, timestamp
            self.timestamp_estimated = estimated
            return image, duration, captured_at
        except Exception as exc:
            self.fail(str(exc))
            raise VideoInputError(self.error) from exc

    def restart(self):
        self.close()
        self._open()
        self.start()

    def fail(self, message):
        self.error = message
        self.state = 'error'
        self.close()

    def cancel(self):
        self.state = 'cancelled'
        self._pending = None
        self.close()

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    @property
    def status(self):
        total = str(self.total) if self.total is not None else '?'
        progress = f' ({min(100, (self.index + 1) * 100 / self.total):.1f}%)' if self.total else ''
        label = {'ready':'Pronto', 'running':'Em andamento', 'paused':'Pausado',
                 'completed':'Concluido', 'cancelled':'Cancelado', 'error':'Erro'}[self.state]
        return (f'{label}: quadro {self.index + 1}/{total}{progress} | '
                f'{self.timestamp_ms / 1000:.2f}s' + (' (estimado por FPS)' if self.timestamp_estimated else '')
                + (f' | {self.error}' if self.error else ''))
