import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, BrowserEquivalent
from .gui_backend import GUIBackend


class WhatsappDesktopAdapter(AdapterBase):
    """
    Example: uses window focus + keyboard sequences.
    """

    WINDOW_TITLE = "WhatsApp"
    PLATFORM_ALIASES = ["whatsapp"]
    # Phase 2g: points at the real WhatsAppWebAdapter -- data declaration
    # only. Not yet consulted by anything: resolution_gate.py's Q2 branch
    # stays 2-way until Phase 2g has a handful of real, tested adapters
    # to validate the 3-way branch against (whatsapp_web_adapter.py,
    # telegram_web_adapter.py are the first two).
    BROWSER_EQUIVALENT = BrowserEquivalent(
        url_template="https://web.whatsapp.com", browser_adapter_key="whatsapp_web"
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
        if self.dry_run:
            self.log_action("open_app", {"target": "whatsapp", "dry_run": True})
            return True
        activated = self.backend.activate_window(self.WINDOW_TITLE)
        time.sleep(0.2)
        self.log_action("open_app", {"target": "whatsapp", "success": activated})
        return activated

    def send_message(self, target: str, message: str) -> bool:
        self.log_action(
            "send_message_start",
            {"target": target, "message": message, "dry_run": self.dry_run},
        )
        if self.dry_run:
            return True
        if not self.open_app():
            return False
        self.backend.hotkey("ctrl", "f")
        time.sleep(0.1)
        self.backend.type_text(target)
        self.backend.press("enter")
        time.sleep(0.2)
        self.backend.type_text(message)
        self.backend.press("enter")
        self.log_action("send_message_end", {"target": target})
        return True

    def close_app(self) -> bool:
        if self.dry_run:
            self.log_action("close_app", {"dry_run": True})
            return True
        closed = self.backend.close_window(self.WINDOW_TITLE)
        if not closed:
            self.log_action("close_app_skipped", {"reason": f"{self.WINDOW_TITLE} not found/focused"})
        return closed

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.log_action("read_unread", {"limit": limit, "dry_run": self.dry_run})
        if self.dry_run:
            return []
        text = self.backend.read_visible_text()
        if not text:
            return []
        return [{"id": "wa-0", "from": "contact", "text": text[:500], "timestamp": time.time()}]
