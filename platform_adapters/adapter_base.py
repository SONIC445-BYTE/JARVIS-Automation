import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ActionSpec:
    """
    Declares one action an adapter supports and the natural-language verbs
    that trigger it. This is what lets a platform's action set grow (e.g.
    Netflix play/pause) without touching central router code -- adapters
    declare what they support, CommandRouter only resolves against those
    declarations. See docs/command_architecture.md.
    """
    name: str
    verbs: List[str]
    requires_target: bool = False
    requires_message: bool = False


class AdapterBase(ABC):
    """
    Minimal adapter interface. Adapters MUST NOT perform destructive actions
    without respecting the daemon dry_run flag and logs.
    """

    # Natural-language names this adapter's platform is known by, e.g.
    # ["whatsapp"]. Matched case-insensitively as a substring of the
    # command text by CommandRouter.
    PLATFORM_ALIASES: List[str] = []

    # Actions this adapter supports, declared by subclasses. The base four
    # (open_app/close_app/send_message/read_unread) are required by the
    # abstract methods below; subclasses may declare additional actions
    # here as they gain platform-specific methods beyond the base four.
    ACTIONS: List[ActionSpec] = []

    def __init__(self, logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run

    @classmethod
    def supports(cls, action_name: str) -> bool:
        return any(spec.name == action_name for spec in cls.ACTIONS)

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
