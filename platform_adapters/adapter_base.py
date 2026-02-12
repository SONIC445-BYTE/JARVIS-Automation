import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AdapterBase(ABC):
    """
    Minimal adapter interface. Adapters MUST NOT perform destructive actions
    without respecting the daemon dry_run flag and logs.
    """

    def __init__(self, logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run

    @abstractmethod
    def open_app(self) -> bool:
        """Open the target app/window. Return True on success."""
        raise NotImplementedError

    @abstractmethod
    def close_app(self) -> bool:
        """Close the target app/window gracefully."""
        raise NotImplementedError

    @abstractmethod
    def send_message(self, target: str, message: str) -> bool:
        """Send a message to target (username/number/channel)."""
        raise NotImplementedError

    @abstractmethod
    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent messages as list of dicts {id, from, text, timestamp}"""
        raise NotImplementedError

    def log_action(self, action: str, meta: Dict[str, Any] = None) -> None:
        self.logger.info({"action": action, "meta": meta, "ts": time.time()})
