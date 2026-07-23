import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, BrowserEquivalent
from .gui_backend import GUIBackend


class TelegramDesktopAdapter(AdapterBase):
    WINDOW_TITLE = "Telegram"
    PLATFORM_ALIASES = ["telegram"]
    # Phase 2g: data declaration only, see whatsapp_desktop_adapter.py's
    # comment on this same field for the standing rule.
    BROWSER_EQUIVALENT = BrowserEquivalent(
        url_template="https://web.telegram.org/k/", browser_adapter_key="telegram_web"
    )
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
        # Found live: this used to only try activate_window(), with no
        # fallback to actually launch the app -- every other adapter
        # (text_editor/browser/calculator/gmail_browser directly,
        # amazon/google/spotify/twitter/youtube via their shared
        # _navigate() helper) falls back to a real launch command when
        # no window is found. A freshly-installed Telegram with no prior
        # window silently failed to open at all. Confirmed live: the
        # non-Store Telegram Desktop installer always places the exe at
        # %APPDATA%\Telegram Desktop\Telegram.exe.
        if self.backend.activate_window(self.WINDOW_TITLE):
            return True
        return self.backend.open_command('start "" "%APPDATA%\\Telegram Desktop\\Telegram.exe"')

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "telegram", "dry_run": self.dry_run})
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
