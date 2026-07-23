import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase
from .gui_backend import GUIBackend


class GmailBrowserAdapter(AdapterBase):
    WINDOW_TITLE = "Gmail"
    GMAIL_URL = "https://mail.google.com/"
    PLATFORM_ALIASES = ["gmail"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["send", "email", "mail"], requires_target=True, requires_message=True),
        ActionSpec("read_unread", verbs=["read", "unread", "check"]),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "gmail", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        if self.backend.activate_window(self.WINDOW_TITLE):
            return True
        return self.backend.open_command(f"start {self.GMAIL_URL}")

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "gmail", "dry_run": self.dry_run})
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
        if not self.open_app():
            return False
        # Generic keyboard navigation for compose flow.
        self.backend.hotkey("c")
        time.sleep(0.2)
        self.backend.type_text(target)
        self.backend.press("tab")
        self.backend.type_text(message)
        self.backend.hotkey("ctrl", "enter")
        self.log_action("send_message_end", {"target": target})
        return True

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.log_action("read_unread", {"limit": limit, "dry_run": self.dry_run})
        if self.dry_run:
            return []
        text = self.backend.read_visible_text().strip()
        if not text:
            return []
        return [{"id": "gmail-0", "from": "inbox", "text": text[:500], "timestamp": time.time()}]
