"""
Phase 2g: unit tests for platform_adapters/browser_automation.py's
CAPTCHA/login-wall detection and shared-session singleton, with a fake
Playwright page (no real browser launch, no network) -- fast, deterministic,
CI-safe. Live-verified behavior (real WhatsApp/Telegram Web navigation) is
documented in docs/phase2g_browser_automation.md, not re-proven here; these
tests pin down the pure logic (marker matching, poll/timeout behavior,
singleton lifecycle) that live testing can't cheaply repeat on every run.
"""
import time
import unittest
from unittest import mock

from platform_adapters.browser_automation import (
    BlockedError,
    BrowserSession,
    get_shared_session,
    reset_shared_session,
)


class FakePage:
    """Stands in for playwright.sync_api.Page. body_text/url/title_text
    are mutable so a test can simulate a page that "settles" into a
    blocked state after N polls (the exact race check_blocked's poll
    loop exists to handle)."""

    def __init__(self, url="https://example.com", title_text="", body_text=""):
        self.url = url
        self._title = title_text
        self._body = body_text

    def title(self):
        return self._title

    def inner_text(self, _selector):
        return self._body


def _session_with_page(page: FakePage) -> BrowserSession:
    # Build a BrowserSession without running __init__ (which launches a
    # real Playwright browser) -- we only want to exercise check_blocked()
    # and the other page-driving methods against a fake page.
    session = BrowserSession.__new__(BrowserSession)
    session._page = page
    session._closed = False
    return session


class TestCheckBlocked(unittest.TestCase):
    def test_no_markers_returns_normally(self):
        session = _session_with_page(FakePage(body_text="Welcome to the app"))
        session.check_blocked(settle_timeout_s=0.2, poll_interval_s=0.05)  # must not raise

    def test_captcha_marker_raises_with_honest_reason(self):
        session = _session_with_page(FakePage(body_text="Please verify you are human"))
        with self.assertRaises(BlockedError) as ctx:
            session.check_blocked(settle_timeout_s=0.2, poll_interval_s=0.05)
        self.assertIn("CAPTCHA", ctx.exception.reason)
        self.assertIn("continue", ctx.exception.reason)

    def test_login_marker_raises_with_honest_reason(self):
        session = _session_with_page(FakePage(body_text="Scan the QR code with your phone"))
        with self.assertRaises(BlockedError) as ctx:
            session.check_blocked(settle_timeout_s=0.2, poll_interval_s=0.05)
        self.assertIn("log in", ctx.exception.reason)
        self.assertIn("continue", ctx.exception.reason)

    def test_marker_in_url_detected(self):
        session = _session_with_page(FakePage(url="https://example.com/recaptcha/check", body_text=""))
        with self.assertRaises(BlockedError):
            session.check_blocked(settle_timeout_s=0.2, poll_interval_s=0.05)

    def test_marker_in_title_detected(self):
        session = _session_with_page(FakePage(title_text="Please sign in", body_text=""))
        with self.assertRaises(BlockedError):
            session.check_blocked(settle_timeout_s=0.2, poll_interval_s=0.05)

    def test_inner_text_exception_does_not_crash_check(self):
        page = FakePage(body_text="irrelevant")
        page.inner_text = mock.Mock(side_effect=RuntimeError("detached frame"))
        session = _session_with_page(page)
        session.check_blocked(settle_timeout_s=0.2, poll_interval_s=0.05)  # must not raise

    def test_poll_loop_catches_marker_that_appears_after_first_check(self):
        """The exact race check_blocked's poll loop exists to handle: a
        React SPA that hasn't rendered the login wall on the first check
        but has by the second. A single immediate check would miss this."""
        page = FakePage(body_text="")
        session = _session_with_page(page)

        call_count = {"n": 0}
        real_inner_text = page.inner_text

        def flaky_inner_text(selector):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                page._body = "please log in"
            return real_inner_text(selector)

        page.inner_text = flaky_inner_text

        with self.assertRaises(BlockedError):
            session.check_blocked(settle_timeout_s=2.0, poll_interval_s=0.05)
        self.assertGreaterEqual(call_count["n"], 2)

    def test_deadline_respected_when_never_blocked(self):
        session = _session_with_page(FakePage(body_text="all clear"))
        start = time.monotonic()
        session.check_blocked(settle_timeout_s=0.3, poll_interval_s=0.1)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.3)
        self.assertLess(elapsed, 1.5)  # generous CI-safe upper bound


class TestSharedSession(unittest.TestCase):
    def tearDown(self):
        reset_shared_session()

    @mock.patch("platform_adapters.browser_automation.BrowserSession")
    def test_get_shared_session_reuses_existing(self, mock_cls):
        instance = mock.Mock()
        instance.is_closed.return_value = False
        mock_cls.return_value = instance

        first = get_shared_session()
        second = get_shared_session()

        self.assertIs(first, second)
        mock_cls.assert_called_once()

    @mock.patch("platform_adapters.browser_automation.BrowserSession")
    def test_get_shared_session_relaunches_after_close(self, mock_cls):
        closed_instance = mock.Mock()
        closed_instance.is_closed.return_value = True
        fresh_instance = mock.Mock()
        fresh_instance.is_closed.return_value = False
        mock_cls.side_effect = [closed_instance, fresh_instance]

        first = get_shared_session()
        first._BrowserSession__is_closed = True  # not used; is_closed() drives the check
        second = get_shared_session()

        self.assertIsNot(first, second)
        self.assertEqual(mock_cls.call_count, 2)

    @mock.patch("platform_adapters.browser_automation.BrowserSession")
    def test_reset_shared_session_closes_and_clears(self, mock_cls):
        instance = mock.Mock()
        instance.is_closed.return_value = False
        mock_cls.return_value = instance

        get_shared_session()
        reset_shared_session()

        instance.close.assert_called_once()

        # Next call must construct a new instance, not reuse the closed one.
        mock_cls.return_value = mock.Mock(is_closed=mock.Mock(return_value=False))
        get_shared_session()
        self.assertEqual(mock_cls.call_count, 2)


if __name__ == "__main__":
    unittest.main()
