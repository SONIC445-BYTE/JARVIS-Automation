from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

from .adapter_base import AdapterBase
from .gui_backend import GUIBackend


class TextEditorAdapter(AdapterBase):
    WINDOW_TITLE = "Notepad"

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "text_editor", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        if self.backend.activate_window(self.WINDOW_TITLE):
            return True
        if os_is_mac():
            return self.backend.open_command("open -a TextEdit")
        if sys.platform.startswith("linux"):
            return self.backend.open_command("gedit")
        return self.backend.open_command("start notepad")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "text_editor", "dry_run": self.dry_run})
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
        self.backend.type_text(message)
        self.backend.press("enter")
        self.log_action("send_message_end", {"target": target})
        return True

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.log_action("read_unread", {"limit": limit, "dry_run": self.dry_run})
        if self.dry_run:
            return []
        text = self.backend.read_visible_text().strip()
        if not text:
            return []
        return [{"id": "editor-0", "from": "editor", "text": text[:500], "timestamp": time.time()}]


def os_is_mac() -> bool:
    return sys.platform == "darwin"
