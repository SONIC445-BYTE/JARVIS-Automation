"""
Phase 2g: WhatsApp Web browser-equivalent adapter -- for when the native
whatsapp_desktop app isn't installed. Real Playwright automation against
the actual web.whatsapp.com, not a placeholder (see Phase 2c-prime:
AgentCore/ui_agent/inspector/browser_adapter.py's self.driver was never
real; this is a from-scratch implementation against a genuine driver).

NOT wired into resolution_gate.py's Q2 branch yet (stays 2-way per the
standing rule) -- this adapter is built and tested standalone.

What's live-verified vs. not, honestly: navigating to the real site and
detecting its real login wall (the QR-code screen every fresh session
shows) was verified live against web.whatsapp.com in this environment.
The send flow PAST that login wall (locators, click sequence, the
"input box clears" completion signal) is real, structured code using
Playwright's role-based locators -- not fake/simulated -- but could not
be live-verified end-to-end in this environment, since doing so
requires pairing a real phone/account with the browser session (no
phone available here to scan the QR code). Treat the locators as
best-effort against WhatsApp Web's known accessibility roles, not
confirmed against a live authenticated session -- flag for follow-up
verification once a real account is available, don't assume it's
proven to the same standard as the block-detection path.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .adapter_base import ActionSpec, AdapterBase, BrowserEquivalent
from .browser_automation import get_shared_session

WHATSAPP_WEB_URL = "https://web.whatsapp.com"


class WhatsAppWebAdapter(AdapterBase):
    PLATFORM_ALIASES = ["whatsapp web"]
    ACTIONS = [
        ActionSpec("open_app", verbs=["open", "launch", "start"]),
        ActionSpec("close_app", verbs=["close", "quit", "exit"]),
        ActionSpec("send_message", verbs=["send", "message", "text"], requires_target=True, requires_message=True),
    ]
    BROWSER_EQUIVALENT = BrowserEquivalent(url_template=WHATSAPP_WEB_URL, browser_adapter_key="whatsapp_web")

    def __init__(self, logger, dry_run: bool = False, session=None):
        super().__init__(logger=logger, dry_run=dry_run)
        self._session = session  # injected for tests; get_shared_session() otherwise

    def _get_session(self):
        return self._session or get_shared_session()

    def open_app(self) -> bool:
        self.log_action("open_app", {"target": "whatsapp_web", "dry_run": self.dry_run})
        if self.dry_run:
            return True
        session = self._get_session()
        session.goto(WHATSAPP_WEB_URL)
        session.check_blocked()  # raises BlockedError -- propagates, not swallowed
        return True

    def close_app(self) -> bool:
        self.log_action("close_app", {"target": "whatsapp_web", "dry_run": self.dry_run})
        return True  # the shared session persists across adapters; nothing to "close" per-adapter

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
        session.goto(WHATSAPP_WEB_URL)
        session.check_blocked()

        # Find the chat: search box -> type contact name -> select result.
        if not session.click_role("textbox", name="Search input textbox"):
            self.log_action("send_message_failed", {"reason": "search box not found"})
            return False
        session.page.keyboard.type(query_target)
        time.sleep(1.0)
        if not session.click_text(query_target):
            self.log_action("send_message_failed", {"reason": f"no chat found for {query_target!r}"})
            return False
        time.sleep(0.5)

        # Type and send the message.
        compose = session.page.get_by_role("textbox", name="Type a message")
        try:
            compose.click(timeout=5000)
            compose.type(text)
            session.press("Enter")
        except Exception as e:
            self.log_action("send_message_failed", {"reason": str(e)})
            return False

        # Concrete completion signal: WhatsApp Web clears the compose
        # box after a message is sent. Not "no exception was thrown" --
        # an actual, observable post-condition.
        time.sleep(1.0)
        try:
            remaining = compose.inner_text().strip()
        except Exception:
            remaining = None
        sent = remaining == ""
        self.log_action("send_message_end", {"target": query_target, "success": sent})
        return sent

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []  # not declared in ACTIONS; base contract requires an implementation
