import threading
import time

class MicArbitrator:
    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None
        
    def acquire(self, owner_id, timeout=5.0):
        start = time.time()
        # Non-blocking acquire with manual timeout loop if needed, 
        # or threading.Lock.acquire(timeout=...) IF supported by platform/py version (Py3+ supports it)
        got = self._lock.acquire(timeout=timeout)
        if not got:
            return False
        self._owner = owner_id
        return True
        
    def release(self, owner_id):
        if self._owner == owner_id:
            self._owner = None
            try:
                self._lock.release()
            except RuntimeError:
                # Already released
                pass
            return True
        return False
        
    def force_release(self):
        try:
            self._lock.release()
        except Exception:
            pass
        self._owner = None
