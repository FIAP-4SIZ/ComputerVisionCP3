"""MediaPipe Hands opcional e flexão por dedo para parâmetros OSC de avatar."""
from dataclasses import dataclass
from hand_quality import HandQualitySettings, plausible_hand
import math
import numpy as np
from pythonosc.osc_bundle_builder import OscBundleBuilder, IMMEDIATELY
from pythonosc.osc_message_builder import OscMessageBuilder
from osc_hands import load_profile, validate_profile, hand_messages

FINGERS = {'Thumb': (1, 2, 3, 4), 'Index': (5, 6, 7, 8),
           'Middle': (9, 10, 11, 12), 'Ring': (13, 14, 15, 16),
           'Little': (17, 18, 19, 20)}
SIDES = ('Left', 'Right')


def finger_curls(landmarks):
    """0 aberto, 1 flexionado: soma de duas mudanças de direção / pi."""
    if len(landmarks) != 21:
        raise ValueError('Esperados 21 pontos da mao')
    p = np.array([[v.x, v.y, v.z] for v in landmarks], dtype=float)
    if not np.isfinite(p).all():
        raise ValueError('Pontos nao finitos')
    values = {}
    for name, chain in FINGERS.items():
        segments = np.diff(p[list(chain)], axis=0)
        lengths = np.linalg.norm(segments, axis=1)
        if np.any(lengths < 1e-8):
            raise ValueError('Articulacoes coincidentes')
        segments /= lengths[:, None]
        angle = sum(math.acos(float(np.clip(np.dot(a, b), -1, 1)))
                    for a, b in zip(segments, segments[1:]))
        values[name] = float(np.clip(angle / math.pi, 0, 1))
    return values


def finger_spreads(landmarks):
    """Abertura lateral: ângulo projetado na palma / 45 graus, limitado a 1.

    A direção neutra de cada dedo é punho→base; a direção observada é
    base→articulação seguinte. Projeção remove a componente normal à palma.
    Projeções degeneradas são omitidas, sem fabricar abertura lateral.
    """
    p = np.asarray([[v.x, v.y, v.z] for v in landmarks], dtype=float)
    if p.shape != (21, 3) or not np.isfinite(p).all():
        raise ValueError('Esperados 21 pontos finitos')
    normal = np.cross(p[5] - p[0], p[17] - p[0])
    length = np.linalg.norm(normal)
    if length < 1e-8:
        return {}
    normal /= length
    values = {}
    for name, chain in FINGERS.items():
        base, following = chain[:2]
        vectors = np.stack((p[base] - p[0], p[following] - p[base]))
        vectors -= (vectors @ normal)[:, None] * normal
        lengths = np.linalg.norm(vectors, axis=1)
        if np.any(lengths < 1e-8):
            continue
        a, b = vectors / lengths[:, None]
        values[name] = float(np.clip(math.acos(float(np.clip(a @ b, -1, 1))) / (math.pi / 4), 0, 1))
    return values


@dataclass
class HandFrame:
    side: str
    score: float
    points: object
    curls: dict
    spreads: object = None
    world_points: object = None


class FingerTracking:
    def __init__(self, detector, client=None, settings=HandQualitySettings(), profile=None):
        self.detector = detector
        self.client = client
        self.settings = settings
        self.profile = load_profile() if profile is None else validate_profile(profile)
        self._settings_used = settings
        self._previous = {}
        self._counts = {}
        self._mirrored = None
        self.status = 'Maos: sem dados'
        self._suspended = False

    def process(self, rgb, mirrored=False):
        # Hands espera imagem selfie. Pose e os backends corporais não mudam.
        if self.settings != self._settings_used or (self._mirrored is not None and mirrored != self._mirrored):
            self.reset()
        self._settings_used = self.settings
        self._mirrored = mirrored
        source = rgb if mirrored else np.ascontiguousarray(rgb[:, ::-1])
        result = self.detector.process(source)
        frames = {}
        image_hands = result.multi_hand_landmarks or []
        world_hands = result.multi_hand_world_landmarks or []
        labels = result.multi_handedness or []
        duplicates = set()
        for image, world, handedness in zip(image_hands, world_hands, labels):
            if not handedness.classification:
                continue
            try:
                classification = handedness.classification[0]
                side, score = classification.label, float(classification.score)
            except (AttributeError, TypeError, ValueError, OverflowError):
                continue
            if side not in SIDES or not math.isfinite(score) or not self.settings.min_handedness <= score <= 1:
                continue
            if side in frames:
                duplicates.add(side)
            try:
                curls = finger_curls(world.landmark)
                points = np.array([[p.x, p.y, p.z] for p in image.landmark], dtype=float)
                if points.shape != (21, 3) or not np.isfinite(points).all():
                    continue
                if not mirrored:
                    points[:, 0] = 1 - points[:, 0]
                if np.any((points[:, :2] < 0) | (points[:, :2] > 1)):
                    continue
                spatial = np.array([[p.x,p.y,p.z] for p in world.landmark], dtype=float)
                if not plausible_hand(points, spatial, rgb.shape, self.settings):
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if side not in frames or score > frames[side].score:
                camera_spatial=spatial.copy()
                if not mirrored:
                    camera_spatial[:,0]*=-1  # Restaura o mesmo referencial da imagem usada pelo Pose.
                frames[side] = HandFrame(side, score, points, curls, finger_spreads(world.landmark), camera_spatial)
        for side in duplicates:
            frames.pop(side, None)  # Lateralidade ambígua não deve animar duas mãos.
        previous, counts, accepted = {}, {}, {}
        for side, frame in frames.items():
            pixels = frame.points[:, :2] * [rgb.shape[1], rgb.shape[0]]
            palm = np.linalg.norm(pixels[5] - pixels[17])
            old = self._previous.get(side)
            close = old is not None and np.linalg.norm(pixels[0] - old[0]) <= self.settings.max_step_palms * min(palm, old[1])
            counts[side] = self._counts.get(side, 0) + 1 if close else 1
            previous[side] = (pixels[0].copy(), palm)
            if counts[side] >= self.settings.confirmation_frames:
                accepted[side] = frame
        self._previous, self._counts = previous, counts
        frames = accepted
        self._suspended = False
        self.publish(frames)
        self.status = ' | '.join(f"{'Esquerda' if side == 'Left' else 'Direita'}: " + ('ok' if side in frames else 'ausente') for side in SIDES)
        return frames

    def publish(self, frames):
        if self.client is None:
            return
        bundle = OscBundleBuilder(IMMEDIATELY)
        accepted = {}
        for side in SIDES:
            frame = frames.get(side)
            if frame is not None:
                # Última barreira antes da rede; não publica flexão inválida.
                try:
                    valid = frame.side == side and set(frame.curls) == set(FINGERS)
                    valid = valid and all(not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1
                                          for v in frame.curls.values())
                except (AttributeError, TypeError, ValueError, OverflowError):
                    valid = False
                if not valid:
                    frame = None
            if frame is not None:
                accepted[side] = frame
        messages = hand_messages(self.profile, accepted)
        for address, value in messages:
            message = OscMessageBuilder(address=address)
            message.add_arg(value)
            bundle.add_content(message.build())
        if messages:
            self.client.send(bundle.build())

    def suspend(self):
        self._previous.clear()
        self._counts.clear()
        if not self._suspended:
            self.publish({})
            self._suspended = True
            self.status = 'Maos: pausadas/sem entrada'

    def reset(self):
        self._previous.clear()
        self._counts.clear()
        self.publish({})
        self.detector.reset()

    def close(self):
        try:
            self.publish({})
        finally:
            self.detector.close()


def draw_hands(image, frames):
    import cv2
    height, width = image.shape[:2]
    for frame in frames.values():
        pixels = np.rint(frame.points[:, :2] * [width-1, height-1]).astype(int)
        for chain in FINGERS.values():
            chain = (0,) + chain
            for a, b in zip(chain, chain[1:]):
                cv2.line(image, tuple(pixels[a]), tuple(pixels[b]), (255, 100, 0), 2)
        for point in pixels:
            cv2.circle(image, tuple(point), 2, (255, 255, 0), -1)
        x, y = pixels[0]
        side = 'Esquerda' if frame.side == 'Left' else 'Direita'
        labels = dict(zip(FINGERS, ('P','I','M','A','N')))
        text = side + ' ' + ' '.join(f'{labels[k]}:{v:.2f}' for k, v in frame.curls.items())
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, .35, (255, 255, 0), 1)
