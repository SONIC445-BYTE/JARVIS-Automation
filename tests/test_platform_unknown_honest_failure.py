"""
Item 2 of the five-item loop instruction: PLATFORM_UNKNOWN honest-failure
fix. Root cause named in the v3.14 live smoke test (see
JARVIS_EXECUTION_LOG.md's "Two real findings surfaced live" entry, finding
#2) and reproduced live there with "open warfare": ResolutionGate.check()
correctly returns GateOutcome.PLATFORM_UNKNOWN when no recognized platform
matches the text, but IntentRouter.classify() silently fell through to
ACTION_PATTERNS/ODAVLoop's generic OBSERVE/DECIDE/ACT pipeline for it --
whose open_app fallback (UIExecutor._open_app) shells out via
subprocess.Popen(target, shell=True) with no honest check, surfacing
Windows' own cryptic error almost verbatim instead of a physician-facing
message.

Fix: classify() now recognizes the open/close-verb subset of
PLATFORM_UNKNOWN (open/close + a name) and routes it to a new
"action_platform_unknown" handler -- the same honest-failure shape as
action_no_adapter/action_not_installed -- instead of falling through.
Anything else under PLATFORM_UNKNOWN (not an open/close attempt at all
-- plain chat, questions, a wired platform's name mentioned without a
launch verb) must keep falling through unchanged; that's still the
correct, intentional design ResolutionGate's own docstring describes.

Deliberately narrower than the full open/close/launch/start/run
ACTION_PATTERNS subset: "launch"/"start"/"run" collide with real, higher-
priority phrasings checked later in classify() -- CODE_PATTERNS' "run
(the) tests/checks" and RHINAL_START_CASE_PATTERNS' "start a new case:
...", both confirmed misrouted here during this fix's own test run
before being narrowed to open/close only. Those collisions are tested
below as explicit non-regressions, not just asserted away in the source
comment.
"""
import unittest

from AgentCore.intent_router import IntentRouter


class TestPlatformUnknownHonestFailure(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_open_unrecognized_target_gets_honest_failure_not_raw_fallthrough(self):
        # The exact v3.14 reproduction.
        intent = self.router.classify("open warfare")
        self.assertEqual(intent.handler, "action_platform_unknown")
        self.assertEqual(intent.extracted_entities["attempted_target"], "warfare")

    def test_covers_both_open_and_close(self):
        for verb in ("open", "close"):
            with self.subTest(verb=verb):
                intent = self.router.classify(f"{verb} zzznonexistentapp123")
                self.assertEqual(intent.handler, "action_platform_unknown")
                self.assertEqual(
                    intent.extracted_entities["attempted_target"],
                    "zzznonexistentapp123",
                )

    def test_run_and_start_and_launch_are_deliberately_not_covered(self):
        # Real collisions found and fixed during this change: "run" and
        # "start" are claimed by higher-priority phrasings checked later
        # in classify() (CODE_PATTERNS' "run tests"/"run checks",
        # RHINAL_START_CASE_PATTERNS' "start a new case: ..."). Pinning
        # these here so a future widening of PLATFORM_UNKNOWN_LAUNCH_
        # PATTERN back to the full verb set doesn't silently reintroduce
        # them.
        self.assertEqual(self.router.classify("run tests").handler, "code_engine")
        self.assertEqual(self.router.classify("run checks").handler, "code_engine")
        self.assertEqual(
            self.router.classify("start a new case: knee pain").handler,
            "rhinal_start_case",
        )
        # "launch"/"start" (outside the RHINAL case-start phrasing) have
        # no dedicated higher-priority handler today, so they fall
        # through to the pre-existing generic ACTION_PATTERNS path,
        # unchanged by this fix -- not the new honest-failure handler.
        self.assertNotEqual(
            self.router.classify("launch the deployment script").handler,
            "action_platform_unknown",
        )
        self.assertNotEqual(
            self.router.classify("start the server").handler,
            "action_platform_unknown",
        )

    def test_known_wired_platform_still_resolves_normally(self):
        # Regression guard: a real, catalog-recognized launch command
        # must not be caught by this new branch.
        intent = self.router.classify("open notepad")
        self.assertNotEqual(intent.handler, "action_platform_unknown")

    def test_plain_chat_with_no_launch_verb_still_falls_through(self):
        # PLATFORM_UNKNOWN fires for this text too (no platform named at
        # all), but it's not a launch attempt -- must still reach llm/chat,
        # not the new honest-failure handler.
        intent = self.router.classify("what is the capital of France?")
        self.assertNotEqual(intent.handler, "action_platform_unknown")

    def test_wired_platform_mentioned_without_a_launch_verb_still_falls_through(self):
        # Mirrors test_resolution_gate.py's
        # test_wired_platform_with_unmatched_verb_does_not_claim_no_adapter:
        # "whatsapp" is wired, but this phrasing has no launch verb at
        # all, so PLATFORM_UNKNOWN fires and correctly is NOT a launch
        # attempt -- must not regress into a false honest-failure claim.
        intent = self.router.classify("whatsapp is a messaging app")
        self.assertNotEqual(intent.handler, "action_platform_unknown")

    def test_non_launch_action_verbs_are_unaffected(self):
        # click/scroll/type/etc. are generic UI actions, never platform
        # launches -- must keep going through the untouched generic
        # ACTION_PATTERNS path regardless of PLATFORM_UNKNOWN.
        for text in ("click the submit button", "scroll down", "type hello world"):
            with self.subTest(text=text):
                intent = self.router.classify(text)
                self.assertNotEqual(intent.handler, "action_platform_unknown")


if __name__ == "__main__":
    unittest.main()
