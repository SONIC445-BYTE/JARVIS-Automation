
# AgentCore/knowledge/network_guard.py

import socket
import time
from contextlib import contextmanager

def internet_available(timeout: float = 2.0) -> bool:
    """Check internet connectivity via DNS lookup."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout)
        return True
    except (socket.timeout, socket.error):
        return False

@contextmanager
def rate_limiter(domain: str):
    """Simple rate limiter placeholder (can be expanded)."""
    # In a real impl, this would track requests per domain
    time.sleep(1.0) # Conservative 1s sleep
    yield
