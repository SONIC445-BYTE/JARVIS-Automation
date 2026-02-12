from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

from .adapter_base import AdapterBase
from .gui_backend import GUIBackend


class BrowserAdapter(AdapterBase):
    WINDOW_TITLE = "Chrome"

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
        self.backend.close_window()
        return True

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
