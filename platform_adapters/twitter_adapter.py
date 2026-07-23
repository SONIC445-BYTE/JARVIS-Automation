"""
Phase 2d: ported from AgentCore/platform_adapters/twitter (audit
class-b -- real compose-intent URL, but never completed the actual
"post" verb; detect_ui also checked `"x" in title`, which matches
almost any window title). Fixed here with Twitter/X's real Ctrl+Enter
post shortcut (same convention as Gmail's Ctrl+Enter send) -- no
coordinate-based clicking needed. The daemon contract has no detect_ui
concept, so that specific bug doesn't carry over.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, extract_query
from .gui_backend import GUIBackend

COMPOSE_URL = "https://twitter.com/intent/tweet?text="


class TwitterAdapter(AdapterBase):
    WINDOW_TITLE = "Twitter"
    # "tweet" included so "post a tweet saying X" resolves without the
    # user having to say "twitter" explicitly -- a natural phrasing gap
    # found via testing, not from the original audit folder.
    PLATFORM_ALIASES = ["twitter", "twitter/x", "tweet"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["post", "tweet"], requires_message=True),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        return self._navigate("https://twitter.com")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "twitter", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        closed = self.backend.close_window(self.WINDOW_TITLE)
        if not closed:
            self.log_action("close_app_skipped", {"reason": f"{self.WINDOW_TITLE} not found/focused"})
        return closed

    def send_message(self, target: str, message: str) -> bool:
        """Posts a tweet. Opens the real compose-intent URL pre-filled,
        then completes the post via Ctrl+Enter -- the audit-flagged gap
        (AgentCore/platform_adapters/twitter stopped at "opens pre-filled,
        doesn't complete")."""
        text = extract_query(target, message, self.PLATFORM_ALIASES)
        self.log_action("send_message_start", {"message": text, "dry_run": self.dry_run})
        if not text:
            self.log_action("send_message_failed", {"reason": "no message extracted", "target": target, "message": message})
            return False
        url = COMPOSE_URL + urllib.parse.quote(text)
        if not self._navigate(url):
            return False
        time.sleep(1.0)  # allow the compose page to load
        self.backend.hotkey("ctrl", "enter")
        self.log_action("send_message_end", {"success": True})
        return True

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []  # not applicable; not declared in ACTIONS

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
