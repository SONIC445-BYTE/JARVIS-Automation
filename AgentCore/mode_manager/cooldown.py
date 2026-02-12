import time

class Cooldown:
    def __init__(self, seconds=2):
        self.seconds = seconds
        self._last_ts = 0
        
    def allow(self):
        now = time.time()
        if now - self._last_ts < self.seconds:
            return False
        self._last_ts = now
        return True
