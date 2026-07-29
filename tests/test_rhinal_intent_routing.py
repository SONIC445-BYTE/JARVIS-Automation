"""
RHINAL MCP integration -- IntentRouter's rhinal_capture pattern branch.

Same style as test_intent_router_code_patterns.py: pins the natural
phrasings that must route to rhinal_capture, confirms no collision with
the pre-existing pattern lists (ACTION/CODE/QUESTION), and confirms the
extraction contract (empty capture_text on a bare trigger phrase is an
honest "nothing to extract" signal, not silently dropped or crashed on).
"""
import unittest

from AgentCore.intent_router import IntentRouter


class TestRhinalCapturePatterns(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def _classify(self, text):
        return self.router.classify(text)

    def test_natural_phrasings_route_to_rhinal_capture(self):
        phrasings = [
            "remember that the vendor meeting moved to Thursday",
            "remember this: check the lab results before Friday",
            "capture this thought: the new UI feels cluttered",
            "capture that thought about caching",
            "save this to my vault: interesting idea about retries",
            "save that to my vault",
            "log this decision: we chose Postgres over Mongo",
            "log that idea",
            "note this down",
            "note that down",
            "add this to my vault",
            "add that to vault",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                self.assertEqual(self._classify(text).handler, "rhinal_capture")

    def test_capture_text_extracted_for_inline_content(self):
        intent = self._classify("remember that the vendor meeting moved to Thursday")
        self.assertEqual(intent.extracted_entities["capture_text"], "the vendor meeting moved to Thursday")

    def test_capture_text_strips_colon_and_whitespace(self):
        intent = self._classify("capture this thought:   the new UI feels cluttered  ")
        self.assertEqual(intent.extracted_entities["capture_text"], "the new UI feels cluttered")

    def test_capture_text_empty_when_trigger_has_no_inline_content(self):
        # "remember this" with nothing after it -- an honest empty
        # extraction, not a crash, not silently dropped. The dispatcher
        # (jarvis.py) is responsible for turning this into a spoken
        # clarification, not this layer.
        intent = self._classify("remember this")
        self.assertEqual(intent.extracted_entities["capture_text"], "")

    def test_non_capture_phrasings_do_not_route_to_rhinal_capture(self):
        phrasings = [
            "open notepad",
            "what is the weather like today",
            "write a python function to check primes",
            "remember to buy milk",  # "remember to X" != "remember that/this X" -- not a supported trigger shape
            "I remember when we started this project",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                self.assertNotEqual(self._classify(text).handler, "rhinal_capture")

    def test_rhinal_capture_checked_before_generic_action_patterns(self):
        # "note this down" would otherwise be at risk of colliding with
        # nothing in ACTION_PATTERNS today, but this pins the intended
        # priority explicitly so a future ACTION_PATTERNS addition can't
        # silently steal it without a visible test failure here.
        intent = self._classify("note this down: circle back with finance next week")
        self.assertEqual(intent.handler, "rhinal_capture")


if __name__ == "__main__":
    unittest.main()
