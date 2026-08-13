"""
RHINAL 13-tool wiring phase -- IntentRouter's pattern branches for the 12
tools other than rhinal_capture/rhinal_attach_file.

Same style as test_rhinal_intent_routing.py: pins the natural phrasings that
must route to each dedicated handler, confirms the extraction contract for
each argument shape (single free-text group, no-argument, and the two
named-group tools), and confirms no collision with the pre-existing pattern
lists (in particular ACTION_PATTERNS' bare "^start\\s+", which would
otherwise swallow "start a new case: X" as a generic, adapter-less action).
"""
import unittest

from AgentCore.intent_router import IntentRouter


class TestRhinalReadOnlyToolRouting(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def _classify(self, text):
        return self.router.classify(text)

    def test_recall(self):
        intent = self._classify("recall what did I say about dengue fluid management")
        self.assertEqual(intent.handler, "rhinal_recall")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "what did I say about dengue fluid management")

    def test_recall_alternate_phrasing(self):
        intent = self._classify("what did i say about the antibiotic protocol")
        self.assertEqual(intent.handler, "rhinal_recall")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "the antibiotic protocol")

    def test_ask_vault(self):
        intent = self._classify("ask my vault what did I decide about triage order")
        self.assertEqual(intent.handler, "rhinal_ask_vault")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "what did I decide about triage order")

    def test_classify_worthiness(self):
        intent = self._classify("would this be worth saving: patient had an unusual reaction")
        self.assertEqual(intent.handler, "rhinal_classify_worthiness")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "patient had an unusual reaction")

    def test_confront(self):
        intent = self._classify("confront my vault with: I believe X causes Y")
        self.assertEqual(intent.handler, "rhinal_confront")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "I believe X causes Y")

    def test_get_calibration_score_sends_no_entities(self):
        for text in ("what's my calibration score", "what is my calibration score", "how calibrated am i"):
            with self.subTest(text=text):
                intent = self._classify(text)
                self.assertEqual(intent.handler, "rhinal_get_calibration_score")
                self.assertEqual(intent.extracted_entities, {})

    def test_get_case_graph_without_id_lists(self):
        intent = self._classify("show my cases")
        self.assertEqual(intent.handler, "rhinal_get_case_graph")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "")

    def test_check_contradiction_extracts_notion_id(self):
        intent = self._classify("check record abc-123 for contradictions")
        self.assertEqual(intent.handler, "rhinal_check_contradiction")
        self.assertEqual(intent.extracted_entities["notion_id"], "abc-123")


class TestRhinalWriteCapableToolRouting(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def _classify(self, text):
        return self.router.classify(text)

    def test_decision_log(self):
        intent = self._classify("log this decision: we chose Postgres over Mongo")
        self.assertEqual(intent.handler, "rhinal_decision_log")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "we chose Postgres over Mongo")

    def test_idea_to_spec_via_turn_into_spec(self):
        intent = self._classify("turn this into a spec: build a triage dashboard")
        self.assertEqual(intent.handler, "rhinal_idea_to_spec")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "build a triage dashboard")

    def test_idea_to_spec_via_log_idea(self):
        intent = self._classify("log that idea")
        self.assertEqual(intent.handler, "rhinal_idea_to_spec")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "")

    def test_start_case_does_not_collide_with_bare_action_start(self):
        """ACTION_PATTERNS has a bare "^start\\s+" pattern -- this must not
        win, or "start a new case: X" would be reported as
        action_no_adapter (no "case" adapter exists) instead of reaching
        rhinal_start_case."""
        intent = self._classify("start a new case called Dengue Outbreak Review")
        self.assertEqual(intent.handler, "rhinal_start_case")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "Dengue Outbreak Review")

    def test_start_case_colon_form(self):
        intent = self._classify("start a case: Dengue Outbreak Review")
        self.assertEqual(intent.handler, "rhinal_start_case")
        self.assertEqual(intent.extracted_entities["rhinal_text"], "Dengue Outbreak Review")

    def test_tag_prediction_extracts_notion_id_and_confidence_as_int(self):
        intent = self._classify("tag record abc-123 as a prediction with 80 percent confidence")
        self.assertEqual(intent.handler, "rhinal_tag_prediction")
        self.assertEqual(intent.extracted_entities["notion_id"], "abc-123")
        self.assertEqual(intent.extracted_entities["confidence"], 80)
        self.assertIsInstance(intent.extracted_entities["confidence"], int)

    def test_resolve_prediction_extracts_notion_id_and_lowercased_outcome(self):
        intent = self._classify("resolve prediction abc-123 as Correct")
        self.assertEqual(intent.handler, "rhinal_resolve_prediction")
        self.assertEqual(intent.extracted_entities["notion_id"], "abc-123")
        self.assertEqual(intent.extracted_entities["outcome"], "correct")

    def test_resolve_prediction_only_matches_known_outcomes(self):
        # "as done" isn't one of RHINAL's enum values (correct/partial/
        # incorrect) -- must not match and silently send a bad outcome.
        intent = self._classify("resolve prediction abc-123 as done")
        self.assertNotEqual(intent.handler, "rhinal_resolve_prediction")


class TestRhinalOtherToolsDoNotCollideWithUnrelatedPatterns(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def _classify(self, text):
        return self.router.classify(text)

    def test_ordinary_questions_still_reach_llm(self):
        intent = self._classify("what is the treatment for dengue shock syndrome")
        self.assertEqual(intent.handler, "llm")

    def test_ordinary_open_command_still_reaches_action_paths(self):
        intent = self._classify("open notepad")
        self.assertIn(intent.handler, ("action", "action_no_adapter", "action_not_installed"))
        self.assertNotIn(
            intent.handler,
            ("rhinal_recall", "rhinal_ask_vault", "rhinal_start_case", "rhinal_get_case_graph"),
        )


if __name__ == "__main__":
    unittest.main()
