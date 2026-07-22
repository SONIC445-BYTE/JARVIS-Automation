"""
Phase 2a: CommandRouter unit tests.

Confirms text resolves to the right (adapter, action, target, message)
Intent by matching adapter-declared platform aliases and action verbs,
covering both the "no messaging verb exists anywhere" gap this phase
closes and the "saying"-marker parsing daemon/intent_parser.py's
simpler splitter doesn't handle.
"""
import unittest
from AgentCore.command_router import CommandRouter


class TestCommandRouterResolve(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def test_open_browser(self):
        intent = self.router.resolve("open browser")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "browser")
        self.assertEqual(intent.action, "open_app")

    def test_open_chrome_alias(self):
        intent = self.router.resolve("open chrome")
        self.assertEqual(intent.adapter, "browser")
        self.assertEqual(intent.action, "open_app")

    def test_close_notepad(self):
        intent = self.router.resolve("close notepad")
        self.assertEqual(intent.adapter, "text_editor")
        self.assertEqual(intent.action, "close_app")

    def test_send_whatsapp_message_with_saying_marker(self):
        intent = self.router.resolve("send a whatsapp message to mom saying I'll be late")
        self.assertEqual(intent.adapter, "whatsapp_desktop")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "I'll be late")

    def test_send_telegram_message_with_saying_marker(self):
        intent = self.router.resolve("send a telegram message to john saying pick up milk")
        self.assertEqual(intent.adapter, "telegram_desktop")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "john")
        self.assertEqual(intent.message, "pick up milk")

    def test_read_unread_telegram(self):
        intent = self.router.resolve("read unread telegram messages")
        self.assertEqual(intent.adapter, "telegram_desktop")
        self.assertEqual(intent.action, "read_unread")

    def test_send_gmail_email(self):
        intent = self.router.resolve("send a gmail to boss@example.com saying running late")
        self.assertEqual(intent.adapter, "gmail_browser")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "boss@example.com")
        self.assertEqual(intent.message, "running late")

    def test_unknown_platform_returns_none(self):
        self.assertIsNone(self.router.resolve("what is the capital of France?"))

    def test_known_platform_unmatched_verb_returns_none(self):
        # "whatsapp" is a known platform, but no declared verb (open/close/
        # send/read) appears -- should not force a match.
        self.assertIsNone(self.router.resolve("whatsapp is a messaging app"))

    def test_message_body_does_not_collide_with_close_app_verb(self):
        # Regression for the bug found via adversarial testing on
        # 4e55699b: verb matching used to scan the whole raw text
        # including the message payload, so "close" inside the dictated
        # message ("saying check the close date") matched close_app's
        # verb list before send_message's verbs got a chance -- order-
        # dependent on ACTIONS declaration order, not on input meaning.
        intent = self.router.resolve(
            "send a telegram message to john saying check the close date"
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "telegram_desktop")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "john")
        self.assertEqual(intent.message, "check the close date")

    def test_message_body_does_not_collide_with_open_app_verb(self):
        # Second collision pair: "open" inside the dictated message must
        # not shadow send_message just because open_app is earlier in
        # WhatsappDesktopAdapter.ACTIONS declaration order.
        intent = self.router.resolve(
            "send a whatsapp message to mom saying let's open the store together"
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "whatsapp_desktop")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "let's open the store together")


if __name__ == "__main__":
    unittest.main()
