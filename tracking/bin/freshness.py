"""Expira uma entrada sem quadros novos uma vez por interrupção."""
import math


class FrameFreshness:
    def __init__(self, timeout=2.):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Timeout deve ser positivo e finito')
        self.timeout=timeout
        self.last=None
        self.expired=False

    def touch(self, now):
        self.last=now
        self.expired=False

    def expire(self, now):
        if self.last is not None and now-self.last >= self.timeout and not self.expired:
            self.expired=True
            return True
        return False
