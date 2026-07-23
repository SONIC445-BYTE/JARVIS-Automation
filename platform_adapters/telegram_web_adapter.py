"""
Phase 2g: Telegram Web browser-equivalent adapter -- for when the
native telegram_desktop app isn't installed. Real Playwright automation
against the actual web.telegram.org/k/, not a placeholder. See
whatsapp_web_adapter.py's module docstring for the shared design
rationale (Phase 2c-prime findings, live-verification boundary).

What's live-verified vs. not, honestly: navigating to the real site and
detecting its real login wall (the QR-code / phone-number screen a
fresh session shows) was verified live against web.telegram.org in this
environment -- including finding that the actual page text ("Log in by
QR Code", "Scan with Telegram app") didn't match an initial reasonable
guess at the marker strings, which is exactly why this was live-tested
rather than assumed. The send flow past that login wall is real,
structured Playwright code (role-based locators), not fake/simulated,
but not live-verified end-to-end -- pairing a real phone/account with
the browser session isn't possible in this environment.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, BrowserEquivalent
from .browser_automation import get_shared_session

TELEGRAM_WEB_URL = "https://web.telegram.org/k/"


class TelegramWebAdapter(AdapterBase):
    PLATFORM_ALIASES = ["telegram web"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["send", "message", "text"], requires_target=True, requires_message=True),
    ]
    BROWSER_EQUIVALENT = BrowserEquivalent(url_template=TELEGRAM_WEB_URL, browser_adapter_key="telegram_web")

    def __init__(self, logger, dry_run: bool = False, session=None):
        super().__init__(logger=logger, dry_run=dry_run)
        self._session = session

    def _get_session(self):
        return self._session or get_shared_session()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "telegram_web", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        session = self._get_session()
        session.goto(TELEGRAM_WEB_URL)
        session.check_blocked()
        return True

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "telegram_web", "dry_run": self.dry_run})
        return True  # shared session persists across adapters

    def send_message(self, target: str, message: str) -> bool:
        query_target = target if target and target.lower() not in self.PLATFORM_ALIASES else ""
        text = message
        self.log_action("send_message_start", {"target": query_target, "message": text, "dry_run": self.dry_run})
        if not query_target or not text:
            self.log_action("send_message_failed", {"reason": "missing target or message"})
            return False
        if self.dry_run:
            return True

        session = self._get_session()
        session.goto(TELEGRAM_WEB_URL)
        session.check_blocked()

        if not session.click_role("button", name="Search"):
            self.log_action("send_message_failed", {"reason": "search control not found"})
            return False
        session.page.keyboard.type(query_target)
        time.sleep(1.0)
        if not session.click_text(query_target):
            self.log_action("send_message_failed", {"reason": f"no chat found for {query_target!r}"})
            return False
        time.sleep(0.5)

        compose = session.page.get_by_role("textbox", name="Message")
        try:
            compose.click(timeout=5000)
            compose.type(text)
            session.press("Enter")
        except Exception as e:
            self.log_action("send_message_failed", {"reason": str(e)})
            return False

        # Concrete completion signal: Telegram Web clears the compose
        # box after a message is sent.
        time.sleep(1.0)
        try:
            remaining = compose.inner_text().strip()
        except Exception:
            remaining = None
        sent = remaining == ""
        self.log_action("send_message_end", {"target": query_target, "success": sent})
        return sent

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []
