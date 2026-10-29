"""Ajustes opcionais de PDI. A entrada BGR original nunca é alterada."""

from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class LightingSettings:
    mode: str = 'off'
    contrast: float = 1.0
    brightness: float = 0.0
    compare: bool = False

    def __post_init__(self):
        if self.mode not in ('off', 'manual', 'equalize'):
            raise ValueError('Modo de iluminacao invalido')
        for value in (self.contrast, self.brightness):
            try:
                finite = math.isfinite(value)
            except (TypeError, OverflowError):
                finite = False
            if isinstance(value, (bool, str)) or not isinstance(value, (int, float)) or not finite:
                raise ValueError('Brilho e contraste devem ser numeros finitos')
        if not .1 <= self.contrast <= 3 or not -100 <= self.brightness <= 100:
            raise ValueError('Contraste: 0.1 a 3; brilho: -100 a 100')
        if not isinstance(self.compare, bool):
            raise ValueError('Comparacao deve ser booleana')

    def inference_key(self):
        # Mudar apenas a visualização não deve apagar o histórico do detector.
        return (self.mode, self.contrast, self.brightness) if self.mode == 'manual' else (self.mode,)


DEFAULT_LIGHTING = LightingSettings()
LABELS = {'off': 'Original', 'manual': 'Brilho/contraste', 'equalize': 'Equalizar luminancia'}


def validate_bgr(image):
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3
            or image.shape[2] != 3 or image.shape[0] == 0 or image.shape[1] == 0):
        raise ValueError('Esperada imagem BGR uint8 com tres canais e dimensoes positivas')


def resize_for_pose(image, max_size):
    validate_bgr(image)
    if isinstance(max_size, bool) or not isinstance(max_size, int) or max_size <= 0:
        raise ValueError('Tamanho maximo deve ser inteiro positivo')
    height, width = image.shape[:2]
    if max(height, width) <= max_size:
        return image
    ratio = max(height, width) / max_size
    return cv2.resize(image, (max(1, int(width / ratio)), max(1, int(height / ratio))))


def apply_lighting(original, settings=DEFAULT_LIGHTING):
    validate_bgr(original)
    if not isinstance(settings, LightingSettings):
        raise ValueError('Configuracao de iluminacao invalida')
    if settings.mode == 'off':
        return original.copy()
    if settings.mode == 'manual':
        # clip(a*I+b): sem abs(), para valores negativos não virarem brilho positivo.
        adjusted = original.astype(np.float32) * settings.contrast + settings.brightness
        return np.clip(np.rint(adjusted), 0, 255).astype(np.uint8)
    ycrcb = cv2.cvtColor(original, cv2.COLOR_BGR2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)


def comparison_view(original, annotated, settings, preprocess_ms=0.):
    validate_bgr(original)
    validate_bgr(annotated)
    if not isinstance(settings, LightingSettings):
        raise ValueError('Configuracao de comparacao invalida')
    if original.shape != annotated.shape:
        raise ValueError('Comparacao exige imagens com o mesmo tamanho')
    if not settings.compare:
        return annotated
    width = original.shape[1]
    pair = np.hstack((original, annotated))
    # Os rótulos ficam fora dos pixels comparados, sem cobrir o esqueleto/métricas.
    view = cv2.copyMakeBorder(pair, 28, 0, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    cv2.putText(view, 'Original (sem inferencia)', (8, 19), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
    label = f'Entrada: {LABELS[settings.mode]} | PDI:{preprocess_ms:.2f}ms'
    cv2.putText(view, label, (width + 8, 19), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
    return view
