"""Observações no plano da imagem, independentes da calibração de corpo inteiro."""

from dataclasses import dataclass
import math

GROUPS = {
    'shoulders': (11, 12), 'hips': (23, 24),
    'knees': (25, 26), 'ankles': (27, 28), 'feet': (29, 30, 31, 32),
    'left_arm': (11, 13, 15), 'right_arm': (12, 14, 16),
}


@dataclass(frozen=True)
class BodyObservation:
    visible: frozenset
    groups: frozenset
    framing: str
    shoulder_angle_degrees: object = None

    @property
    def status(self):
        labels = {'none': 'Sem pontos visiveis', 'partial': 'Enquadramento parcial',
                  'chest': 'Peitoral visivel', 'full': 'Corpo completo visivel'}
        arms = sum(name in self.groups for name in ('left_arm', 'right_arm'))
        return f'{labels[self.framing]} | bracos:{arms}/2'


def observe_body(landmarks, threshold=.5):
    """Filtra por visibility E enquadramento, sem transformar pixels em metros.

    Pose pode estimar pontos fora da imagem. Eles não são observações visíveis.
    Não substitui a validação 3D: não cria quadris/pernas nem calibra escala.
    """
    if isinstance(threshold, bool):
        raise ValueError('Limiar invalido')
    threshold = float(threshold)
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Limiar invalido')
    if landmarks is None:
        landmarks = []
    if len(landmarks) not in (0, 33):
        raise ValueError('Esperados 33 landmarks de imagem')
    visible = set()
    for i, point in enumerate(landmarks):
        try:
            x, y, z, v = map(float, (point.x, point.y, point.z, point.visibility))
            if all(map(math.isfinite, (x, y, z, v))) and 0 <= x <= 1 and 0 <= y <= 1 and threshold <= v <= 1:
                visible.add(i)
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue
    groups = frozenset(name for name, indices in GROUPS.items() if set(indices) <= visible)
    full = {'shoulders', 'hips', 'knees', 'ankles', 'feet'} <= groups
    framing = 'full' if full else 'chest' if 'shoulders' in groups else 'partial' if visible else 'none'
    angle = None
    if 'shoulders' in groups:
        a, b = landmarks[11], landmarks[12]
        dx, dy = float(b.x) - float(a.x), float(b.y) - float(a.y)
        if math.hypot(dx, dy) > 1e-6:
            # Inclinação no plano normalizado; não é rotação 3D nem ângulo em pixels.
            angle = math.degrees(math.atan2(dy, dx))
    return BodyObservation(frozenset(visible), groups, framing, angle)


def draw_observation(image, landmarks, observation, connections):
    """Desenha somente pontos/conexões visíveis; imagem de exibição já é cópia."""
    import cv2
    height, width = image.shape[:2]
    points = {i: (round(float(landmarks[i].x) * (width - 1)),
                  round(float(landmarks[i].y) * (height - 1))) for i in observation.visible}
    for a, b in connections:
        if a in points and b in points:
            cv2.line(image, points[a], points[b], (0, 220, 0), 2)
    for point in points.values():
        cv2.circle(image, point, 3, (0, 255, 255), -1)
