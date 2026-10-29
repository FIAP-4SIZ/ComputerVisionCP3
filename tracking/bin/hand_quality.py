"""Regras simples e ajustáveis; não são uma medida de acurácia do modelo."""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class HandQualitySettings:
    min_handedness: float = .75
    min_palm_pixels: float = 12.
    confirmation_frames: int = 2
    max_step_palms: float = 2.5

    def __post_init__(self):
        for value in (self.min_handedness, self.min_palm_pixels, self.max_step_palms):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Parâmetros das mãos devem ser números finitos')
        if not .5 <= self.min_handedness <= 1 or not 0 <= self.min_palm_pixels <= 200:
            raise ValueError('Pontuação: 0.5 a 1; tamanho mínimo da palma: 0 a 200 pixels')
        if (type(self.confirmation_frames) is not int or not 1 <= self.confirmation_frames <= 10
                or not .5 <= self.max_step_palms <= 20):
            raise ValueError('Confirmação: 1 a 10 quadros; salto máximo: 0.5 a 20 palmas')


def plausible_hand(points, world, image_shape, settings):
    """Rejeita degeneração e proporções grosseiramente incoerentes.

    Hands não dá visibility por articulação: mesmo uma mão aceita é estimativa.
    Tamanho usa pixels reais; flexão usa estimativa espacial, não profundidade real.
    """
    height, width = image_shape[:2]
    pixels = points[:, :2] * [width, height]
    palm = np.linalg.norm(pixels[5] - pixels[17])
    if palm < max(settings.min_palm_pixels, 1e-6):
        return False
    # Área da palma para evitar punhos/dedos colapsados. Mãos de perfil podem ser
    # rejeitadas: preferimos ausência explícita a uma orientação sem suporte.
    a, b = pixels[5] - pixels[0], pixels[17] - pixels[0]
    if abs(a[0]*b[1] - a[1]*b[0]) < .02 * palm**2:
        return False
    spatial_palm = np.linalg.norm(world[5] - world[17])
    if spatial_palm < 1e-8:
        return False
    for chain in ((1,2,3,4), (5,6,7,8), (9,10,11,12), (13,14,15,16), (17,18,19,20)):
        lengths = np.linalg.norm(np.diff(world[list(chain)], axis=0), axis=1) / spatial_palm
        if np.any(lengths < .02) or np.any(lengths > 2):
            return False
    return True
