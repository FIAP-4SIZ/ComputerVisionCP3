"""Controle desktop explícito: dois braços levantados produzem um pulo OSC."""
import math
from pythonosc.udp_client import SimpleUDPClient
from body_observation import observe_body


class VRChatDesktopBackend:
    def __init__(self):
        self.client = None
        self.pressed = False
        self.deadline = None
        self.count = 0
        self.armed = True
        self.status = 'Desktop: levante os dois bracos para pular'

    def connect(self, params):
        self.client = SimpleUDPClient(params.backend_ip, params.backend_port)
        self.client.send_message('/input/Jump', 0)

    def process_image(self, landmarks, timestamp, threshold=.5):
        if not math.isfinite(timestamp):
            self.invalidate()
            return
        self.tick(timestamp)
        observation = observe_body(landmarks, threshold)
        if not {11,12,13,14,15,16} <= observation.visible:
            self.invalidate()
            self.status = 'Desktop: enquadre ombros, cotovelos e pulsos'
            return
        raised = all(landmarks[w].y < landmarks[s].y-.08 for w,s in ((15,11),(16,12)))
        lowered = all(landmarks[w].y > landmarks[s].y-.02 for w,s in ((15,11),(16,12)))
        if lowered:
            self.armed = True
        self.count = self.count+1 if raised else 0
        if self.armed and self.count >= 3:
            self.client.send_message('/input/Jump', 1)
            self.pressed = True
            self.deadline = timestamp+.15
            self.armed = False
            self.status = 'Desktop: pulo enviado; abaixe os bracos para repetir'

    def tick(self, timestamp):
        if self.pressed and timestamp >= self.deadline:
            self.client.send_message('/input/Jump', 0)
            self.pressed = False

    def invalidate(self):
        self.reset()
        self.armed = False  # Recuperar pontos com braços no alto não dispara ação.

    def reset(self):
        if self.pressed and self.client is not None:
            self.client.send_message('/input/Jump', 0)
        self.pressed = False
        self.deadline = None
        self.count = 0
        self.armed = True

    def disconnect(self):
        self.reset()

    def expire_trackers(self, names):
        pass

    def onparamchanged(self, params):
        pass

    def updatepose(self, *args, **kwargs):
        return True  # Não envia /tracking/trackers nem depende de pernas/quadris.
