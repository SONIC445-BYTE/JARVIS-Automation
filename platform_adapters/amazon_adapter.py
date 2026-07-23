"""
Phase 2d: ported from AgentCore/platform_adapters/amazon (audit class-a
-- real, complete). Search navigates to Amazon's real, documented search
URL (amazon.com/s?k=<query>); no coordinate-based clicking needed.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, extract_query
from .gui_backend import GUIBackend

AMAZON_URL = "https://www.amazon.com"


class AmazonAdapter(AdapterBase):
    WINDOW_TITLE = "Amazon"
    PLATFORM_ALIASES = ["amazon"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["search"], requires_target=True, requires_message=True),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        return self._navigate(AMAZON_URL)

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "amazon", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        closed = self.backend.close_window(self.WINDOW_TITLE)
        if not closed:
            self.log_action("close_app_skipped", {"reason": f"{self.WINDOW_TITLE} not found/focused"})
        return closed

    def send_message(self, target: str, message: str) -> bool:
        query = extract_query(target, message, self.PLATFORM_ALIASES)
        if not query:
            self.log_action("send_message_failed", {"reason": "no query extracted", "target": target, "message": message})
            return False
        url = f"{AMAZON_URL}/s?k={urllib.parse.quote(query)}"
        self.log_action("send_message_start", {"target": query, "dry_run": self.dry_run})
        return self._navigate(url)

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []  # not applicable to Amazon; not declared in ACTIONS

    def _navigate(self, url: str) -> bool:
        self.log_action("navigate", {"url": url, "dry_run": self.dry_run})
        if self.dry_run:
            return True
        if not self.backend.activate_window("Chrome"):
            self.backend.open_command("start chrome")
            time.sleep(1.0)
        self.backend.hotkey("ctrl", "l")
        time.sleep(0.1)
        self.backend.type_text(url)
        self.backend.press("enter")
        return True
