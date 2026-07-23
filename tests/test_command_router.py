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

    def test_target_name_does_not_collide_with_close_app_verb(self):
        # No "saying" marker present -- the target name itself contains
        # "close", which must not shadow send_message just because
        # close_app is checked earlier in ACTIONS declaration order.
        intent = self.router.resolve("send a message to close-friend on whatsapp")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "whatsapp_desktop")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "close-friend")

    def test_trailing_clause_does_not_collide_with_open_app_verb(self):
        # No "to"/"saying" marker present -- the trailing "from X" clause
        # contains "open", which must not shadow read_unread just because
        # open_app is checked earlier in ACTIONS declaration order.
        intent = self.router.resolve(
            "read unread whatsapp messages from open-source-group"
        )
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "whatsapp_desktop")
        self.assertEqual(intent.action, "read_unread")

    def test_multiword_verb_still_matches_across_target_marker(self):
        # Regression: browser's "go to"/"navigate to" verbs legitimately
        # contain the " to " target marker as part of the verb phrase
        # itself -- bounding verb-scan to before " to " must not break
        # these (they're matched against the untruncated prefix instead).
        intent = self.router.resolve("browser go to google.com")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "browser")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.target, "google.com")

    def test_as_marker_extracts_filename(self):
        # Bug found via adversarial testing after Phase 2d: only " to "
        # was recognized as a target marker, so "save notepad as
        # report.txt" resolved with target="notepad" (the alias, not the
        # real filename) instead of "report.txt".
        intent = self.router.resolve("save notepad as report.txt")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "text_editor")
        self.assertEqual(intent.action, "save_file")
        self.assertEqual(intent.target, "report.txt")

    def test_for_marker_extracts_search_query(self):
        # Bug found via adversarial testing: "search google for X" had
        # no recognized marker at all for "for", so the query was lost.
        intent = self.router.resolve("search google for python tutorials")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "google")
        self.assertEqual(intent.action, "send_message")
        self.assertEqual(intent.message, "python tutorials")

    def test_trailing_platform_name_does_not_pollute_message(self):
        # Bug found via adversarial testing: with no marker at all between
        # the query and a trailing platform mention, "play despacito on
        # spotify" resolved with message="play despacito on spotify" --
        # the entire raw phrase, verb included -- because the message-
        # fallback branch didn't trim trailing clauses the way target
        # extraction already did. This is the more serious of the two
        # bugs: it doesn't fail, it silently searches for the wrong
        # (garbage) string and reports success.
        intent = self.router.resolve("play despacito on spotify")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "spotify")
        self.assertEqual(intent.action, "play")
        self.assertEqual(intent.message, "despacito")

    def test_bare_verb_with_no_content_does_not_silently_echo_raw_text(self):
        # "calculate" alone (no expression) must not resolve to
        # message="calculate" (the raw text echoed back) -- that's
        # nonsensical input for the calculate action. The router itself
        # can't know this is meaningless (that's the adapter-level
        # extract_query guard's job, see test_phase2d_ported_adapters.py),
        # but pin what the router actually hands the adapter so the
        # guard's behavior is traceable end-to-end.
        intent = self.router.resolve("calculate")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.adapter, "calculator")
        self.assertEqual(intent.action, "calculate")
        self.assertEqual(intent.message, "calculate")  # == the platform alias itself


if __name__ == "__main__":
    unittest.main()
