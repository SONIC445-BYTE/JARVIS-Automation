r"""
D13: IntentRouter.classify() misrouted informational "search for X"
phrasings to handler="action" instead of "llm". The original
ACTION_PATTERNS entry r"^search\s+(?:for\s+)?" matched unconditionally
-- checked before QUESTION_PATTERNS -- so any "search for X" won
regardless of what followed, even a bare "search for the definition of
recursion and explain it" with no platform named for resolution_gate to
have caught first.

Found during S0-E1's conversational-layer audit, reconfirmed live
against the current classify() before this fix (2026-07-30), fixed
here by restricting the ACTION pattern to phrasings with an explicit
action-continuation verb ("...and open/click/visit/go to...") -- the
actual signal that distinguishes "go do a UI action on the results"
from "search for information and tell me about it."
"""
import unittest
from AgentCore.intent_router import IntentRouter


class TestSearchPhraseRouting(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def _handler(self, text):
        return self.router.classify(text).handler

    def test_informational_search_phrasings_route_to_llm(self):
        phrasings = [
            "search for the definition of recursion and explain it",
            "search for python tutorials",
            "search for the causes of anasarca",
            "search for today's weather",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                self.assertEqual(self._handler(text), "llm")

    def test_search_with_an_explicit_action_continuation_still_routes_to_action(self):
        # The one case that must NOT regress: a search that explicitly
        # asks for a follow-up UI action on the result is still a real
        # action request, not an informational one.
        phrasings = [
            "search for restaurants near me and open the first one",
            "search for the JARVIS repo and click the first link",
            "search for flight deals and visit the top result",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                self.assertEqual(self._handler(text), "action")

    def test_platform_named_search_still_reaches_the_resolution_gate(self):
        # "search amazon for X" names a specific platform, so it's
        # resolved before the generic ACTION_PATTERNS fallback this fix
        # touches -- must not regress into "llm" now that the generic
        # bare-search pattern was narrowed.
        intent = self.router.classify("search amazon for shoes")
        self.assertNotEqual(intent.handler, "llm")


if __name__ == "__main__":
    unittest.main()
