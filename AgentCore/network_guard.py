import socket

def internet_available(timeout=2) -> bool:
    """
    Check if internet is available using raw TCP connection to 8.8.8.8 (Google DNS).
    No API, no service overhead.
    """
    try:
        # Check connection to Google DNS
        socket.create_connection(("8.8.8.8", 53), timeout)
        return True
    except OSError:
        return False
    except Exception:
        return False
