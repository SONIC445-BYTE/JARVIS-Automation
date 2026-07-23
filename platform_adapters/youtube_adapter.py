"""
Phase 2d: ported from AgentCore/platform_adapters/youtube (audit
class-b -- real search URL, but "play_video"'s click-through was a
no-op `pass`). Same genuine UIScanner use case as Spotify: no fixed
keyboard shortcut exists for "play this specific search result", so the
first result is found for real via UIScanner rather than guessed. See
Phase 2c-prime investigation and docs/adapter_audit.md.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, extract_query
from .element_finder import find_first_clickable_center
from .gui_backend import GUIBackend

SEARCH_URL = "https://www.youtube.com/results?search_query="


class YouTubeAdapter(AdapterBase):
    WINDOW_TITLE = "YouTube"
    PLATFORM_ALIASES = ["youtube"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["search"], requires_target=True, requires_message=True),
        ActionSpec("play", verbs=["play"], requires_message=True),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        return self._navigate("https://www.youtube.com")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "youtube", "dry_run": self.dry_run})
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
        return self._navigate(SEARCH_URL + urllib.parse.quote(query))

    def play(self, target: str = "", message: str = "") -> bool:
        """Search, then click the first (topmost-then-leftmost) real
        clickable element on the results page -- a video thumbnail has
        no fixed text label, unlike Spotify's "Play" button, so this
        uses position rather than text match. Honest failure if nothing
        clickable was found, never a fake/simulated success (unlike the
        original AgentCore/platform_adapters/youtube, whose click-through
        was a silent no-op that still returned as if it worked).
        extract_query filters out the platform alias / raw-command-
        echoed-back placeholder values found via adversarial testing."""
        query = extract_query(target, message, self.PLATFORM_ALIASES)
        self.log_action("play_start", {"query": query, "dry_run": self.dry_run})
        if not query:
            self.log_action("play_failed", {"reason": "no query extracted", "target": target, "message": message})
            return False
        if self.dry_run:
            return True
        if not self._navigate(SEARCH_URL + urllib.parse.quote(query)):
            return False
        time.sleep(2.0)  # allow search results to render
        center = find_first_clickable_center()
        if center is None:
            self.log_action("play_failed", {"query": query, "reason": "No clickable result found"})
            return False
        self.backend.click(*center)
        self.log_action("play_end", {"query": query, "success": True})
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
