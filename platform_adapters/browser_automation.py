"""
Phase 2g: real browser automation for browser-equivalent adapters.

Uses Playwright (see docs/phase2g_browser_automation.md for the choice
over Selenium and why) with a PERSISTENT browser context per process --
launched once, reused across actions/adapters, not relaunched per
command. This matters for two things: (1) performance (browser launch
is slow), and (2) session/cookie persistence, so a manually-completed
login or CAPTCHA solve (see BlockedError) survives into the next action.

Nothing in AgentCore/ui_agent/inspector/browser_adapter.py is reused --
confirmed dead-on-arrival in Phase 2c-prime (self.driver never
constructed, so every method there either no-ops or fails). This is a
from-scratch implementation against a real driver.
"""
from __future__ import annotations

import threading
import time
from typing import Optional


class BlockedError(Exception):
    """Raised when a page shows a CAPTCHA/login-wall/bot-check. Carries
    an honest, physician-facing explanation of what's blocking progress
    and what to do -- never silently swallowed. Callers must surface
    .reason to the user and wait for an explicit resume signal, not
    retry silently or report a generic failure."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


_lock = threading.Lock()
_session: Optional["BrowserSession"] = None


def get_shared_session(headless: bool = False) -> "BrowserSession":
    """One browser session per process, shared across all browser-
    equivalent adapters, so a login/CAPTCHA solved for one site doesn't
    vanish before the next command. headless=False by default: the
    window must be visible for a physician to actually complete a
    login/CAPTCHA when asked to."""
    global _session
    with _lock:
        if _session is None or _session.is_closed():
            _session = BrowserSession(headless=headless)
        return _session


def reset_shared_session() -> None:
    """Close and drop the shared session (tests only -- production code
    should not need to force a relaunch)."""
    global _session
    with _lock:
        if _session is not None:
            _session.close()
        _session = None


_CAPTCHA_MARKERS = (
    "captcha", "recaptcha", "hcaptcha", "verify you are human",
    "are you a robot", "unusual traffic", "prove you're not a robot",
)
_LOGIN_MARKERS = (
    "sign in to continue", "log in to continue", "please log in",
    "please sign in", "scan this code to log in", "scan the qr code",
    "use whatsapp on your computer",
    # Telegram Web's actual observed text (found via live testing --
    # differs from a reasonable guess: "log in by qr code", not "log in
    # to telegram by qr code").
    "log in by qr code", "scan with telegram app", "log in by phone number",
)


class BrowserSession:
    """Thin wrapper around a single persistent Playwright browser
    context and page. Every method returns bool / raises on genuine
    failure -- no method fakes success."""

    # Found via live testing against the real web.whatsapp.com: with
    # Playwright's default context (no explicit user-agent), WhatsApp
    # Web serves a "your browser is unsupported, update Chrome" wall
    # instead of the real QR login page -- not a documented API
    # decision, an empirically-found requirement to reach the actual
    # site content these adapters need to automate.
    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, headless: bool = False):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._context = self._browser.new_context(user_agent=self._USER_AGENT)
        self._page = self._context.new_page()
        self._closed = False

    @property
    def page(self):
        return self._page

    def is_closed(self) -> bool:
        return self._closed

    def goto(self, url: str, timeout_ms: int = 20000) -> None:
        self._page.goto(url, timeout=timeout_ms)

    def current_url(self) -> str:
        return self._page.url

    def title(self) -> str:
        try:
            return self._page.title()
        except Exception:
            return ""

    def check_blocked(self, settle_timeout_s: float = 6.0, poll_interval_s: float = 0.5) -> None:
        """Raise BlockedError if the current page looks like a CAPTCHA
        or login wall. Heuristic (URL/title/visible-text substring
        match against known markers), not exhaustive -- new block
        patterns will need new markers over time; that's an accepted,
        documented limitation (docs/phase2g_browser_automation.md), not
        a silent gap.

        Polls for up to settle_timeout_s rather than checking once
        immediately after navigation: found via adversarial testing that
        a single immediate check can run before a React-SPA page (e.g.
        WhatsApp Web) has finished rendering, missing a login wall that
        IS present -- worse than a slow check, since it lets a blocked
        action silently proceed to a confusing generic failure ("search
        box not found") instead of the honest, actionable block message.
        A fixed sleep in goto() was considered and rejected: some pages
        render fast (wasted time) and some slower (still insufficient),
        and WhatsApp Web keeps a persistent websocket open, so waiting
        for Playwright's "networkidle" state can hang/timeout on exactly
        the sites this matters most for. Polling adapts to actual
        render time within a bounded cap instead.

        Honest limitation: this is a bounded wait against a live,
        network-dependent page, not a guarantee. Repeated live testing
        (6+ consecutive runs after this poll loop was added) came back
        clean, but one earlier run -- before the 6s budget below -- saw
        a single anomalous miss consistent with a slow server response
        exceeding the wait budget, not a logic bug (a from-scratch,
        bypassing-the-shared-session reproduction of the same scenario
        was clean). settle_timeout_s was widened from 4.0s to 6.0s for
        extra margin; this does not make the check deterministic against
        real-world network variance, and that residual possibility is
        documented rather than hidden."""
        deadline = time.monotonic() + settle_timeout_s
        while True:
            url = self._page.url.lower()
            title = self.title().lower()
            body_text = ""
            try:
                body_text = self._page.inner_text("body")[:3000].lower()
            except Exception:
                pass

            haystack = f"{url} {title} {body_text}"

            for marker in _CAPTCHA_MARKERS:
                if marker in haystack:
                    raise BlockedError(
                        f"This looks like a CAPTCHA/bot check ({marker!r} detected). "
                        f"Please complete it manually in the browser window, then say 'continue'."
                    )
            for marker in _LOGIN_MARKERS:
                if marker in haystack:
                    raise BlockedError(
                        f"This page needs you to log in first ({marker!r} detected). "
                        f"Please log in manually in the browser window, then say 'continue'."
                    )

            if time.monotonic() >= deadline:
                return
            time.sleep(poll_interval_s)

    def click_text(self, text: str, timeout_ms: int = 8000) -> bool:
        """Click the first visible element whose text matches. Real
        Playwright locator with built-in auto-wait -- returns False
        (honest failure) if nothing matched within the timeout."""
        try:
            self._page.get_by_text(text, exact=False).first.click(timeout=timeout_ms)
            return True
        except Exception:
            return False

    def click_role(self, role: str, name: Optional[str] = None, timeout_ms: int = 8000) -> bool:
        try:
            locator = self._page.get_by_role(role, name=name) if name else self._page.get_by_role(role)
            locator.first.click(timeout=timeout_ms)
            return True
        except Exception:
            return False

    def fill(self, selector: str, text: str, timeout_ms: int = 8000) -> bool:
        try:
            self._page.locator(selector).first.fill(text, timeout=timeout_ms)
            return True
        except Exception:
            return False

    def type_into(self, selector: str, text: str, timeout_ms: int = 8000) -> bool:
        """Character-by-character typing (fires real keydown/input
        events), for editors (e.g. WhatsApp Web's message box) that
        don't behave like a plain <input> and don't respond correctly
        to .fill()."""
        try:
            locator = self._page.locator(selector).first
            locator.click(timeout=timeout_ms)
            locator.type(text)
            return True
        except Exception:
            return False

    def press(self, key: str) -> None:
        self._page.keyboard.press(key)

    def wait_for_selector(self, selector: str, timeout_ms: int = 8000) -> bool:
        try:
            self._page.locator(selector).first.wait_for(timeout=timeout_ms)
            return True
        except Exception:
            return False

    def wait_for_url_contains(self, fragment: str, timeout_ms: int = 8000) -> bool:
        try:
            self._page.wait_for_url(f"**{fragment}**", timeout=timeout_ms)
            return True
        except Exception:
            return fragment.lower() in self._page.url.lower()

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._context.close()
            self._browser.close()
            self._playwright.stop()
        except Exception:
            pass
        finally:
            self._closed = True
