import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase
from .gui_backend import GUIBackend


class TelegramDesktopAdapter(AdapterBase):
    WINDOW_TITLE = "Telegram"
    PLATFORM_ALIASES = ["telegram"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["send", "message", "text"], requires_target=True, requires_message=True),
        ActionSpec("read_unread", verbs=["read", "unread", "check"]),
    ]

    def __init__(self, logger, dry_run: bool = False, backend: GUIBackend = None):
        super().__init__(logger=logger, dry_run=dry_run)
        self.backend = backend or GUIBackend()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "telegram", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        return self.backend.activate_window(self.WINDOW_TITLE)

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "telegram", "dry_run": self.dry_run})
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
        if not self.open_app():
            return False
        self.backend.hotkey("ctrl", "k")
        time.sleep(0.1)
        self.backend.type_text(target)
        self.backend.press("enter")
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
        return [{"id": "tg-0", "from": "chat", "text": text[:500], "timestamp": time.time()}]
