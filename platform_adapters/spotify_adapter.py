"""
Phase 2d: ported from AgentCore/platform_adapters/spotify (audit
class-b -- real search URL, but the "click Play on first result" step
was commented out entirely). This is the genuine UIScanner use case
among the 11 ported adapters: unlike Gmail/Twitter's fixed Ctrl+Enter
shortcut, there is no fixed keyboard shortcut for "play this specific
search result" -- its position depends on page state, so it has to be
found for real via AgentCore.ui_perception.UIScanner
(platform_adapters/element_finder.py), not guessed. See Phase 2c-prime
investigation and docs/adapter_audit.md.
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase
from .element_finder import find_element_center
from .gui_backend import GUIBackend

SEARCH_URL = "https://open.spotify.com/search/"


class SpotifyAdapter(AdapterBase):
    WINDOW_TITLE = "Spotify"
    PLATFORM_ALIASES = ["spotify"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["search"], requires_target=True),
        ActionSpec("play", verbs=["play"], requires_message=True),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        return self._navigate("https://open.spotify.com")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "spotify", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        self.backend.close_window()
        return True

    def send_message(self, target: str, message: str) -> bool:
        query = target or message
        if not query:
            return False
        return self._navigate(SEARCH_URL + urllib.parse.quote(query))

    def play(self, target: str = "", message: str = "") -> bool:
        """Search, then find and click the real "Play" element on the
        results page -- honest failure (returns False) if it can't be
        found, never a fake/simulated success."""
        query = message or target
        self.log_action("play_start", {"query": query, "dry_run": self.dry_run})
        if not query:
            return False
        if self.dry_run:
            return True
        if not self._navigate(SEARCH_URL + urllib.parse.quote(query)):
            return False
        time.sleep(2.0)  # allow search results to render
        center = find_element_center("Play")
        if center is None:
            self.log_action("play_failed", {"query": query, "reason": "Play element not found"})
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
