import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BrowserEquivalent:
    """
    Declares that this platform's requested action can also be performed
    via a browser (Phase 2g), for use when the native app isn't
    installed. Phase 2c-prime groundwork only -- NOT wired into
    resolution_gate.py's Q2 branch yet (stays a plain install-or-nothing
    offer until Phase 2g has real, verified adapters to activate the
    3-way branch against). See docs/resolution_gate.md.
    """
    url_template: str        # e.g. "https://web.whatsapp.com"
    browser_adapter_key: str  # key into the Phase 2g browser-adapter registry


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


def extract_query(target: str, message: str, platform_aliases: List[str], raw_text: str = "") -> str:
    """
    Pick whichever of target/message is genuine extracted content for a
    search/play/post-style action, filtering out placeholder values that
    signal extraction failed rather than the user genuinely wanting to
    search for that literal text:
      - empty
      - exactly equal to one of this platform's own aliases (the
        CommandRouter fallback value when no real target was extracted)
      - the entire raw command echoed back verbatim (extraction found no
        marker at all and gave up)

    Returns "" if neither target nor message is usable -- callers must
    treat that as an honest failure (return False / report "I didn't
    understand what to search for"), never proceed with a bad value.
    Found via adversarial testing on "play despacito on spotify" and
    "search google for X" resolving to garbage/alias values instead of
    the real query -- see docs/command_architecture.md.
    """
    aliases_lower = {a.lower() for a in platform_aliases}
    raw_lower = raw_text.strip().lower()

    def is_real(value: str) -> bool:
        if not value:
            return False
        value_lower = value.strip().lower()
        if value_lower in aliases_lower:
            return False
        if raw_lower and value_lower == raw_lower:
            return False
        return True

    if is_real(message):
        return message.strip()
    if is_real(target):
        return target.strip()
    return ""


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

    # None (the default -- true for nearly everything until Phase 2g
    # builds adapters) means no browser fallback is offered when the
    # native app isn't installed.
    BROWSER_EQUIVALENT: Optional[BrowserEquivalent] = None

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
