from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase
from .gui_backend import GUIBackend


class BrowserAdapter(AdapterBase):
    WINDOW_TITLE = "Chrome"
    PLATFORM_ALIASES = ["browser", "chrome"]
    ACTIONS = [
        # new_tab/close_tab declared before open_app/close_app: "close tab"
        # must not be shadowed by close_app's single-word "close" verb --
        # first-match-wins in CommandRouter, so the more specific
        # multi-word verb needs to be checked first. See
        # docs/command_architecture.md.
        ActionSpec("new_tab", verbs=["new tab"]),
        ActionSpec("close_tab", verbs=["close tab"]),
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["go to", "navigate to", "search"], requires_target=True),
        ActionSpec("read_unread", verbs=["read"]),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "browser", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        if self.backend.activate_window(self.WINDOW_TITLE):
            return True
        if sys.platform == "darwin":
            return self.backend.open_command("open -a 'Google Chrome'")
        if sys.platform.startswith("linux"):
            return self.backend.open_command("google-chrome")
        return self.backend.open_command("start chrome")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "browser", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        closed = self.backend.close_window(self.WINDOW_TITLE)
        if not closed:
            self.log_action("close_app_skipped", {"reason": f"{self.WINDOW_TITLE} not found/focused"})
        return closed

    def send_message(self, target: str, message: str) -> bool:
        self.log_action(
            "send_message_start",
            {"target": target, "message": message, "dry_run": self.dry_run},
        )
        if self.dry_run:
            return True
        self.open_app()
        self.backend.hotkey("ctrl", "l")
        time.sleep(0.1)
        if target.startswith("http://") or target.startswith("https://"):
            self.backend.type_text(target)
        else:
            self.backend.type_text(f"https://www.google.com/search?q={message}")
        self.backend.press("enter")
        self.log_action("send_message_end", {"target": target, "success": True})
        return True

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.log_action("read_unread", {"limit": limit, "dry_run": self.dry_run})
        if self.dry_run:
            return []
        text = self.backend.read_visible_text().strip()
        if not text:
            return []
        return [{"id": "browser-0", "from": "visible_window", "text": text[:500], "timestamp": time.time()}]

    def new_tab(self, target: str = "", message: str = "") -> bool:
        """Ported from AgentCore/platform_adapters/chrome (class-a, real).
        Ctrl+T is Chrome's real, reliable new-tab shortcut -- no
        coordinate-based clicking needed. target/message unused --
        custom actions are called uniformly as method(target, message)."""
        self.log_action("new_tab", {"dry_run": self.dry_run})
        if self.dry_run:
            return True
        if not self.open_app():
            return False
        self.backend.hotkey("ctrl", "t")
        return True

    def close_tab(self, target: str = "", message: str = "") -> bool:
        """Ctrl+W is Chrome's real, reliable close-tab shortcut."""
        self.log_action("close_tab", {"dry_run": self.dry_run})
        if self.dry_run:
            return True
        self.backend.hotkey("ctrl", "w")
        return True
