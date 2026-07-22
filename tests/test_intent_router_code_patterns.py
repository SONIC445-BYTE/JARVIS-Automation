"""
Phase 1: CODE_PATTERNS regex coverage.

The original patterns were anchored as ^verb (fixed-noun-list) with no
tolerance for an article or adjective between the verb and the noun, so
they missed most natural phrasing -- including the exact commands used
in the JARVIS diagnosis brief's own Phase 1 Definition of Done ("write a
python script that...", "create a function that..."). This pins the
fixed behavior so it doesn't regress back to the brittle version.
"""
import unittest
from AgentCore.intent_router import IntentRouter


class TestCodePatternsMatchNaturalPhrasing(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def _handler(self, text):
        return self.router.classify(text).handler

    def test_natural_coding_phrasings_route_to_code_engine(self):
        phrasings = [
            "write a python script that sorts a list",
            "create a function that adds two numbers",
            "build a script that scrapes a website",
            "generate a function that reverses a string",
            "implement a binary search",
            "add a function to X",
            "fix the bug in parser",
            "fix bug in parser",
            "refactor the login module",
            "write test for the parser",
            "run tests",
            "propose a patch for this",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                self.assertEqual(self._handler(text), "code_engine")

    def test_non_coding_phrasings_do_not_route_to_code_engine(self):
        phrasings = [
            "open notepad",
            "create a new folder",
            "add a contact",
            "build a resume",
            "write a birthday message",
            "what is the capital of France?",
            "search for python tutorials",
        ]
        for text in phrasings:
            with self.subTest(text=text):
                self.assertNotEqual(self._handler(text), "code_engine")


if __name__ == "__main__":
    unittest.main()
