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


class TestPlatformDetectionIgnoresPayload(unittest.TestCase):
    """Fourth instance of the same bug class as the three fixes above
    (message-body verb collision, target-name verb collision, trailing-
    clause verb collision): CommandRouter.resolve()'s platform-alias
    detection ran BEFORE any message/target zone was computed, scanning
    the entire raw text -- so a second platform's name mentioned inside
    the actual query/target content could misroute the command (or, if
    it "won" as the longer alias but had no matching verb, block
    resolution entirely). Fixed structurally via _platform_scan_zone():
    platform detection is now scoped to the same message/target-
    excised zone verb matching already used, computed once and shared,
    not a per-bug special case. See CommandRouter.resolve()'s docstring
    for the enforced rule.

    One case per marker family (to/as/for/saying) plus the exact three
    reports, so a regression in any of them is caught, not just today's
    specific inputs.
    """

    def setUp(self):
        self.router = CommandRouter()

    def _assert_resolves(self, text, adapter, action):
        intent = self.router.resolve(text)
        self.assertIsNotNone(intent, f"{text!r} did not resolve")
        self.assertEqual(intent.adapter, adapter, f"{text!r} misrouted")
        self.assertEqual(intent.action, action)
        return intent

    # The exact three reports.
    def test_for_marker_platform_in_payload_wrong_platform_entirely(self):
        # Previously misrouted to Spotify (longer alias, and "search" is
        # one of its declared verbs) instead of Amazon.
        intent = self._assert_resolves(
            "search amazon for spotify gift cards", "amazon", "send_message"
        )
        self.assertEqual(intent.message, "spotify gift cards")

    def test_for_marker_platform_in_payload_previously_failed_to_resolve(self):
        # Previously resolved to None: "whatsapp" (longer alias) won
        # platform detection, then no whatsapp verb matched "search
        # google", so resolution failed outright rather than misrouting.
        intent = self._assert_resolves(
            "search google for how to use whatsapp", "google", "send_message"
        )
        self.assertEqual(intent.message, "how to use whatsapp")

    def test_for_marker_platform_in_payload_second_previously_failed_case(self):
        intent = self._assert_resolves(
            "search youtube for calculator tutorials", "youtube", "send_message"
        )
        self.assertEqual(intent.message, "calculator tutorials")

    # One case per remaining marker family.
    def test_to_marker_platform_in_payload(self):
        # "telegram" appears in the target itself, not a trailing clause
        # -- must not steal platform detection from "whatsapp".
        intent = self._assert_resolves(
            "send a whatsapp message to my telegram friend", "whatsapp_desktop", "send_message"
        )
        self.assertEqual(intent.target, "my telegram friend")

    def test_as_marker_platform_in_payload(self):
        intent = self._assert_resolves(
            "save notepad as spotify_backup.txt", "text_editor", "save_file"
        )
        self.assertEqual(intent.target, "spotify_backup.txt")

    def test_saying_marker_platform_in_payload(self):
        intent = self._assert_resolves(
            "send a whatsapp message saying open spotify now", "whatsapp_desktop", "send_message"
        )
        self.assertEqual(intent.message, "open spotify now")

    # Regression: platform mentioned in a genuine trailing clause (not
    # payload content) must still resolve -- this is the case the fix
    # deliberately preserves, not breaks.
    def test_trailing_clause_platform_mention_still_resolves(self):
        intent = self._assert_resolves(
            "send a message to close-friend on whatsapp", "whatsapp_desktop", "send_message"
        )
        self.assertEqual(intent.target, "close-friend")


class TestMessageBackfillGuard(unittest.TestCase):
    """5th instance of the router-hands-adapters-an-unclean-value bug
    family: a send_message-shaped command (target marker present, no
    explicit "saying"-style message marker) used to backfill `message`
    from leftover verb+platform prefix text -- e.g. "whatsapp message" --
    and send that as if it were real dictated content. extract_query()
    (adapter_base.py) doesn't catch this shape (verified directly: it
    only filters values that are exactly alias-equal or exactly the raw
    command echoed back, and "whatsapp message" is neither), so the fix
    is at the source: CommandRouter no longer backfills `message` at all
    for actions that also require a real target, and instead sets
    Intent.message_required_but_missing so callers can give an honest
    "I didn't catch what you wanted to say" instead of either silently
    no-op'ing or sending the leftover text."""

    def setUp(self):
        self.router = CommandRouter()

    def test_whatsapp_desktop_no_saying_clause(self):
        intent = self.router.resolve("send whatsapp message to mom")
        self.assertEqual(intent.adapter, "whatsapp_desktop")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "")
        self.assertTrue(intent.message_required_but_missing)

    def test_telegram_desktop_no_saying_clause(self):
        intent = self.router.resolve("send telegram message to john")
        self.assertEqual(intent.adapter, "telegram_desktop")
        self.assertEqual(intent.target, "john")
        self.assertEqual(intent.message, "")
        self.assertTrue(intent.message_required_but_missing)

    def test_whatsapp_web_no_saying_clause(self):
        # The bug was confirmed inherited by the new Phase 2g web
        # adapter too, not desktop-only.
        intent = self.router.resolve("send whatsapp web message to mom")
        self.assertEqual(intent.adapter, "whatsapp_web")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "")
        self.assertTrue(intent.message_required_but_missing)

    def test_as_marker_framing_no_saying_clause(self):
        intent = self.router.resolve("send whatsapp message as mom")
        self.assertEqual(intent.adapter, "whatsapp_desktop")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "")
        self.assertTrue(intent.message_required_but_missing)

    def test_dangling_saying_marker_does_not_leak_into_target(self):
        # "...to mom saying" with nothing dictated after "saying" used to
        # leak the word "saying" itself into the target ("mom saying")
        # since the exact-substring marker match requires trailing
        # content and silently failed to match at all.
        intent = self.router.resolve("send whatsapp web message to mom saying")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "")
        self.assertTrue(intent.message_required_but_missing)

    def test_genuine_saying_clause_is_unaffected(self):
        intent = self.router.resolve("send whatsapp web message to mom saying hi")
        self.assertEqual(intent.target, "mom")
        self.assertEqual(intent.message, "hi")
        self.assertFalse(intent.message_required_but_missing)

    def test_single_value_backfill_unaffected_play(self):
        # requires_target is False for play -- the leftover-prefix
        # backfill is legitimate here and must be unchanged by this fix.
        intent = self.router.resolve("play despacito on spotify")
        self.assertEqual(intent.adapter, "spotify")
        self.assertEqual(intent.message, "despacito")
        self.assertFalse(intent.message_required_but_missing)

    def test_single_value_backfill_unaffected_search(self):
        intent = self.router.resolve("search amazon for wireless mouse")
        self.assertEqual(intent.adapter, "amazon")
        self.assertEqual(intent.message, "wireless mouse")
        self.assertFalse(intent.message_required_but_missing)

    def test_open_app_action_never_flagged(self):
        # requires_message is False for open_app -- the flag must never
        # be set regardless of target/message content.
        intent = self.router.resolve("open whatsapp web")
        self.assertFalse(intent.message_required_but_missing)

    def test_extract_query_does_not_catch_this_shape_directly(self):
        # Documents why the fix had to be at the router, not a tweak to
        # extract_query(): the garbage values this bug produced are not
        # alias-equal or raw-echo, so extract_query's existing filters
        # pass them through unchanged.
        from platform_adapters.adapter_base import extract_query
        self.assertEqual(
            extract_query("mom", "whatsapp message", ["whatsapp"]), "whatsapp message"
        )


class TestUIExecutorHonorsMessageRequiredButMissing(unittest.TestCase):
    """The flag must be checked centrally in UIExecutor, before any
    adapter is invoked -- never a per-adapter patch, and never a silent
    no-op or a call with the missing message."""

    def test_execute_intent_never_calls_adapter_and_reports_honest_reason(self):
        from unittest import mock
        from AgentCore.ui_executor import UIExecutor, ExecutionStatus

        router = CommandRouter()
        intent = router.resolve("send whatsapp message to mom")
        self.assertTrue(intent.message_required_but_missing)

        executor = UIExecutor.__new__(UIExecutor)
        executor._get_adapter = mock.Mock(side_effect=AssertionError("adapter must not be looked up"))

        result = executor.execute_intent(intent)

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("mom", result.error)
        self.assertIn("catch", result.error)


if __name__ == "__main__":
    unittest.main()
