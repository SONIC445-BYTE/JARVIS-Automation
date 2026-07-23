"""
Phase 2g: unit tests for WhatsAppWebAdapter/TelegramWebAdapter's
send_message logic, with an injected fake BrowserSession (the session=
constructor param exists specifically for this -- see both adapters'
__init__). No real Playwright/browser involved; live navigation and
block-detection against the real sites is covered separately (live
testing, documented in docs/phase2g_browser_automation.md) and by
test_browser_automation.py's check_blocked() unit tests.
"""
import unittest
from unittest import mock

from platform_adapters.browser_automation import BlockedError
from platform_adapters.telegram_web_adapter import TelegramWebAdapter
from platform_adapters.whatsapp_web_adapter import WhatsAppWebAdapter


def _fake_session(chat_found=True, search_found=True, compose_remaining=""):
    session = mock.Mock()
    session.click_role.return_value = search_found
    session.click_text.return_value = chat_found
    compose = mock.Mock()
    compose.inner_text.return_value = compose_remaining
    session.page.get_by_role.return_value = compose
    return session, compose


class AdapterCaseMixin:
    ADAPTER_CLASS = None
    SLEEP_TARGET = None  # module path to patch time.sleep in, to keep tests fast

    def _make(self, session):
        return self.ADAPTER_CLASS(logger=mock.Mock(), dry_run=False, session=session)

    def setUp(self):
        self._sleep_patch = mock.patch(self.SLEEP_TARGET)
        self._sleep_patch.start()
        self.addCleanup(self._sleep_patch.stop)

    def test_missing_target_returns_false_without_touching_session(self):
        session, _ = _fake_session()
        adapter = self._make(session)
        self.assertFalse(adapter.send_message("", "hello"))
        session.goto.assert_not_called()

    def test_missing_message_returns_false_without_touching_session(self):
        session, _ = _fake_session()
        adapter = self._make(session)
        self.assertFalse(adapter.send_message("mom", ""))
        session.goto.assert_not_called()

    def test_target_equal_to_platform_alias_is_treated_as_missing(self):
        # extract_query-style guard: if CommandRouter's target extraction
        # fell back to echoing the platform alias, that's not a real
        # contact name -- must not proceed as if it were.
        session, _ = _fake_session()
        adapter = self._make(session)
        alias = self.ADAPTER_CLASS.PLATFORM_ALIASES[0]
        self.assertFalse(adapter.send_message(alias, "hello"))
        session.goto.assert_not_called()

    def test_dry_run_returns_true_without_touching_session(self):
        session, _ = _fake_session()
        adapter = self.ADAPTER_CLASS(logger=mock.Mock(), dry_run=True, session=session)
        self.assertTrue(adapter.send_message("mom", "hello"))
        session.goto.assert_not_called()

    def test_search_control_not_found_returns_false(self):
        session, _ = _fake_session(search_found=False)
        adapter = self._make(session)
        self.assertFalse(adapter.send_message("mom", "hello"))
        session.click_text.assert_not_called()

    def test_no_chat_found_returns_false(self):
        session, _ = _fake_session(chat_found=False)
        adapter = self._make(session)
        self.assertFalse(adapter.send_message("mom", "hello"))
        session.page.get_by_role.assert_not_called()

    def test_successful_send_detected_via_cleared_compose_box(self):
        session, compose = _fake_session(compose_remaining="")
        adapter = self._make(session)
        self.assertTrue(adapter.send_message("mom", "hello"))
        compose.click.assert_called_once()
        compose.type.assert_called_once_with("hello")
        session.press.assert_called_once_with("Enter")

    def test_compose_box_still_has_text_means_not_sent(self):
        # The concrete completion signal (compose box clears) is absent --
        # must report False, never assume success just because no
        # exception was thrown.
        session, compose = _fake_session(compose_remaining="hello")
        adapter = self._make(session)
        self.assertFalse(adapter.send_message("mom", "hello"))

    def test_compose_click_exception_returns_false(self):
        session, compose = _fake_session()
        compose.click.side_effect = RuntimeError("element detached")
        adapter = self._make(session)
        self.assertFalse(adapter.send_message("mom", "hello"))

    def test_blocked_error_from_check_blocked_propagates_not_swallowed(self):
        # A CAPTCHA/login-wall must surface all the way up as BlockedError,
        # not get caught and turned into a generic False.
        session, _ = _fake_session()
        session.check_blocked.side_effect = BlockedError("please log in")
        adapter = self._make(session)
        with self.assertRaises(BlockedError):
            adapter.send_message("mom", "hello")

    def test_open_app_navigates_and_checks_blocked(self):
        session, _ = _fake_session()
        adapter = self._make(session)
        self.assertTrue(adapter.open_app())
        session.goto.assert_called_once()
        session.check_blocked.assert_called_once()

    def test_open_app_dry_run_skips_session(self):
        session, _ = _fake_session()
        adapter = self.ADAPTER_CLASS(logger=mock.Mock(), dry_run=True, session=session)
        self.assertTrue(adapter.open_app())
        session.goto.assert_not_called()

    def test_open_app_propagates_block(self):
        session, _ = _fake_session()
        session.check_blocked.side_effect = BlockedError("captcha detected")
        adapter = self._make(session)
        with self.assertRaises(BlockedError):
            adapter.open_app()

    def test_close_app_does_not_close_shared_session(self):
        # Shared session persists across adapters/commands by design --
        # close_app must be a no-op on the session, not tear it down.
        session, _ = _fake_session()
        adapter = self._make(session)
        self.assertTrue(adapter.close_app())
        session.close.assert_not_called()


class TestWhatsAppWebAdapter(AdapterCaseMixin, unittest.TestCase):
    ADAPTER_CLASS = WhatsAppWebAdapter
    SLEEP_TARGET = "platform_adapters.whatsapp_web_adapter.time.sleep"


class TestTelegramWebAdapter(AdapterCaseMixin, unittest.TestCase):
    ADAPTER_CLASS = TelegramWebAdapter
    SLEEP_TARGET = "platform_adapters.telegram_web_adapter.time.sleep"


if __name__ == "__main__":
    unittest.main()
