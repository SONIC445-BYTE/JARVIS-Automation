from __future__ import annotations

import sys
import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase
from .gui_backend import GUIBackend


class TextEditorAdapter(AdapterBase):
    WINDOW_TITLE = "Notepad"
    PLATFORM_ALIASES = ["notepad", "text editor", "editor"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["type", "write", "note"], requires_message=True),
        ActionSpec("read_unread", verbs=["read"]),
        ActionSpec("save_file", verbs=["save"], requires_target=True),
    ]

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

    def save_file(self, target: str = "", message: str = "") -> bool:
        """Ported from AgentCore/platform_adapters/notepad (audit
        class-b): the original had hardcoded, explicitly-admitted-guessed
        click coordinates ("# Guess" comments) for the File/Save menu and
        Save button. Ctrl+S is Notepad's real, reliable save shortcut --
        no coordinate-based clicking needed at all, which is a more
        robust fix than routing through UIScanner for a fixed-shortcut
        action. save_file declares requires_target=True (matches the
        established "save notepad to X" phrasing, same "to"-marker
        pattern as send_message elsewhere); if no real filename was
        given, target falls back to the platform alias itself
        ("notepad") -- filtered out below as "no filename provided"
        rather than saved as a literal filename."""
        filename = target if target.lower() not in (a.lower() for a in self.PLATFORM_ALIASES) else ""
        self.log_action("save_file", {"filename": filename, "dry_run": self.dry_run})
        if not filename:
            return False
        if self.dry_run:
            return True
        self.backend.hotkey("ctrl", "s")
        time.sleep(0.4)  # Save As dialog (if this is a new/unsaved file)
        self.backend.type_text(filename)
        self.backend.press("enter")
        return True


def os_is_mac() -> bool:
    return sys.platform == "darwin"
