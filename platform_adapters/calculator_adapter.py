"""
Phase 2d: ported from AgentCore/platform_adapters/calculator (audit
class-b -- real "calculate" logic, but no open_app/close_app declared at
all). Adding those here completes it. All keyboard/subprocess-driven,
no coordinate-based clicking needed.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

import re

from .adapter_base import ActionSpec, AdapterBase, extract_query
from .gui_backend import GUIBackend

# Windows Calculator's text input accepts digits and operator symbols,
# not English words -- "12 times 8" typed literally does not compute.
# The original AgentCore/platform_adapters/calculator folder had this
# same gap (typed the raw expression as-is); fixed here since it's the
# one genuinely new capability added in this porting pass, found via a
# live end-to-end test.
_WORD_OPERATORS = [
    (r"\btimes\b", "*"),
    (r"\bmultiplied by\b", "*"),
    (r"\bplus\b", "+"),
    (r"\badded to\b", "+"),
    (r"\bminus\b", "-"),
    (r"\bdivided by\b", "/"),
    (r"\bover\b", "/"),
]


def _normalize_expression(expression: str) -> str:
    result = expression.lower()
    for pattern, symbol in _WORD_OPERATORS:
        result = re.sub(pattern, symbol, result)
    result = re.sub(r"\s+", "", result)
    return result


class CalculatorAdapter(AdapterBase):
    WINDOW_TITLE = "Calculator"
    # "calculate" included so "calculate 5 plus 3" resolves without the
    # user having to say "calculator" explicitly -- a natural phrasing gap
    # found via testing, not from the original audit folder.
    PLATFORM_ALIASES = ["calculator", "calculate"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("calculate", verbs=["calculate"], requires_message=True),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "calculator", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        if self.backend.activate_window(self.WINDOW_TITLE):
            return True
        return self.backend.open_command("start calc")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "calculator", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        closed = self.backend.close_window(self.WINDOW_TITLE)
        if not closed:
            self.log_action("close_app_skipped", {"reason": f"{self.WINDOW_TITLE} not found/focused"})
        return closed

    def calculate(self, target: str = "", message: str = "") -> bool:
        """Ported from the audit folder's real logic: type the expression,
        press Enter. No coordinates involved. Custom actions are called
        uniformly as method(target, message) -- the expression arrives as
        message (calculate declares requires_message=True)."""
        expression = extract_query(target, message, self.PLATFORM_ALIASES)
        if not expression:
            self.log_action("calculate_failed", {"reason": "no expression extracted", "target": target, "message": message})
            return False
        normalized = _normalize_expression(expression)
        self.log_action("calculate", {"expression": expression, "normalized": normalized, "dry_run": self.dry_run})
        if self.dry_run:
            return True
        if not self.open_app():
            return False
        time.sleep(0.3)
        self.backend.type_text(normalized)
        self.backend.press("enter")
        return True

    def send_message(self, target: str, message: str) -> bool:
        raise NotImplementedError("Calculator has no messaging concept")

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []  # not applicable; not declared in ACTIONS
