"""
RHINAL 13-tool wiring phase -- jarvis.py's dispatch for the 12 tools other
than rhinal_capture (`elif intent.handler in RHINAL_OTHER_HANDLERS:` ->
handle_rhinal_other()).

Same discipline as test_rhinal_dispatch.py / test_rhinal_capture_audit_
wiring.py: these call the real handle_rhinal_other(), not a mirrored copy.
Read-only tools are tested for response-building only (no audit chokepoint
gap to close). The 5 write-capable tools get the same two-tier audit
treatment DEC-002/D16 established, verified the same way: mocked-argument
assertions for the failure-mode matrix, plus one real-audit-log test per
representative tool proving the record actually lands, HMAC-chained,
on disk -- not just that emit_clinical_action was called with the right
kwargs.
"""
import unittest
from unittest import mock

from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError
from jarvis import handle_rhinal_other


def _ok_audit():
    return mock.Mock(ok=True, error=None, queued_to_fallback=False)


class TestReadOnlyToolsBuildHonestResponses(unittest.TestCase):
    def test_recall_reports_top_source_summary(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.recall.return_value = {
                "sources": [{"summary": "Dengue fluid protocol notes"}, {"summary": "second"}]
            }
            response = handle_rhinal_other("rhinal_recall", "recall X", {"rhinal_text": "dengue"})
        m.return_value.recall.assert_called_once_with("dengue")
        self.assertIn("Dengue fluid protocol notes", response)
        self.assertIn("2 sources", response)

    def test_recall_with_no_sources_says_so_honestly(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.recall.return_value = {"sources": []}
            response = handle_rhinal_other("rhinal_recall", "recall X", {"rhinal_text": "nothing"})
        self.assertIn("didn't find anything", response)

    def test_recall_empty_query_asks_for_clarification_without_calling_client(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            response = handle_rhinal_other("rhinal_recall", "recall", {"rhinal_text": ""})
        m.assert_not_called()
        self.assertIn("recall", response.lower())

    def test_ask_vault_reports_top_source_summary(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.ask_vault.return_value = {"sources": [{"summary": "answer material"}]}
            response = handle_rhinal_other("rhinal_ask_vault", "ask my vault X", {"rhinal_text": "question"})
        m.return_value.ask_vault.assert_called_once_with("question")
        self.assertIn("answer material", response)

    def test_classify_worthiness_reports_worthy_verdict(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.classify_worthiness.return_value = {
                "vaultWorthy": True, "confidence": 0.9, "reason": "specific technical detail",
            }
            response = handle_rhinal_other("rhinal_classify_worthiness", "would this be worth saving: X", {"rhinal_text": "X"})
        self.assertIn("worth saving", response)
        self.assertIn("specific technical detail", response)

    def test_classify_worthiness_reports_not_worthy_verdict(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.classify_worthiness.return_value = {"vaultWorthy": False}
            response = handle_rhinal_other("rhinal_classify_worthiness", "X", {"rhinal_text": "X"})
        self.assertIn("probably not worth saving", response)

    def test_confront_with_no_results_says_so(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.confront.return_value = {"noResults": True}
            response = handle_rhinal_other("rhinal_confront", "confront X", {"rhinal_text": "X"})
        self.assertIn("didn't find anything relevant", response)

    def test_confront_reports_real_field_shape_counts(self):
        # Real live-verified shape (execution log's RHINAL 13-tool wiring
        # entry): correct/missed/contradicts/unverified, each a list.
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.confront.return_value = {
                "correct": [{"text": "a"}],
                "missed": [{"text": "b"}],
                "contradicts": [{"text": "c", "explanation": "why"}],
                "unverified": [{"text": "d"}],
                "sources": [{"notionId": "x"}],
            }
            response = handle_rhinal_other("rhinal_confront", "confront X", {"rhinal_text": "X"})
        self.assertIn("1 confirmed", response)
        self.assertIn("1 you missed", response)
        self.assertIn("1 contradicting", response)
        self.assertIn("1 unverified", response)

    def test_get_calibration_score_reports_real_field_names(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.get_calibration_score.return_value = {
                "calibrationScore": 75, "resolvedPredictions": 2, "totalPredictions": 3,
            }
            response = handle_rhinal_other("rhinal_get_calibration_score", "what's my calibration score", {})
        m.return_value.get_calibration_score.assert_called_once_with()
        self.assertIn("75", response)
        self.assertIn("2", response)
        self.assertIn("3", response)

    def test_get_calibration_score_with_no_data_says_so(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.get_calibration_score.return_value = None
            response = handle_rhinal_other("rhinal_get_calibration_score", "x", {})
        self.assertIn("don't have any calibration data", response)

    def test_get_case_graph_without_id_lists_titles(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.get_case_graph.return_value = [{"title": "Case A"}, {"title": "Case B"}]
            response = handle_rhinal_other("rhinal_get_case_graph", "show my cases", {"rhinal_text": ""})
        m.return_value.get_case_graph.assert_called_once_with(case_id=None)
        self.assertIn("2 case graph", response)
        self.assertIn("Case A", response)

    def test_get_case_graph_with_id_reports_node_edge_counts(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.get_case_graph.return_value = {"title": "Case A", "nodeCount": 14, "edgeCount": 1}
            response = handle_rhinal_other("rhinal_get_case_graph", "show case X", {"rhinal_text": "case-123"})
        m.return_value.get_case_graph.assert_called_once_with(case_id="case-123")
        self.assertIn("14", response)
        self.assertIn("1", response)

    def test_check_contradiction_reports_count(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.check_contradiction.return_value = {"contradictions": [{"x": 1}]}
            response = handle_rhinal_other("rhinal_check_contradiction", "check record X", {"notion_id": "abc"})
        m.return_value.check_contradiction.assert_called_once_with("abc")
        self.assertIn("1 contradiction", response)

    def test_call_error_on_a_read_only_tool_is_surfaced_honestly(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.recall.side_effect = RhinalCallError("unreachable")
            response = handle_rhinal_other("rhinal_recall", "recall X", {"rhinal_text": "X"})
        self.assertIn("Couldn't reach Rhinal", response)

    def test_config_error_on_a_read_only_tool_is_surfaced_honestly(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m:
            m.return_value.recall.side_effect = RhinalConfigError("not configured")
            response = handle_rhinal_other("rhinal_recall", "recall X", {"rhinal_text": "X"})
        self.assertIn("not configured", response)


class TestWriteCapableToolsAreAudited(unittest.TestCase):
    """The 5 write-capable tools, same two-record DEC-002 shape as
    rhinal_capture, verified against the real dispatch function."""

    def test_decision_log_emits_two_records_and_saves(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.decision_log.return_value = {"saved": True}
            response = handle_rhinal_other(
                "rhinal_decision_log", "log this decision: chose Postgres", {"rhinal_text": "chose Postgres"})

        m_client.return_value.decision_log.assert_called_once_with("chose Postgres")
        self.assertEqual(m_emit.call_count, 2)
        self.assertEqual(m_emit.call_args_list[0].kwargs["what_action"], "rhinal_decision_log")
        self.assertEqual(m_emit.call_args_list[0].kwargs["outcome_status"], "attempted")
        self.assertEqual(m_emit.call_args_list[1].kwargs["outcome_status"], "success")
        self.assertIn("Logged that decision", response)

    def test_decision_log_empty_text_asks_for_clarification_without_writing_or_auditing(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.emit_clinical_action") as m_emit:
            response = handle_rhinal_other("rhinal_decision_log", "log this decision", {"rhinal_text": ""})
        m_client.assert_not_called()
        m_emit.assert_not_called()
        self.assertIn("didn't catch", response)

    def test_idea_to_spec_emits_two_records_and_saves(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.idea_to_spec.return_value = {"saved": True}
            response = handle_rhinal_other(
                "rhinal_idea_to_spec", "turn this into a spec: dashboard", {"rhinal_text": "dashboard"})

        m_client.return_value.idea_to_spec.assert_called_once_with("dashboard")
        self.assertEqual(m_emit.call_args_list[0].kwargs["what_action"], "rhinal_idea_to_spec")
        self.assertIn("Turned that into a spec", response)

    def test_start_case_emits_two_records_and_reports_title(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.start_case.return_value = {"id": "case-1"}
            response = handle_rhinal_other(
                "rhinal_start_case", "start a case: Outbreak Review", {"rhinal_text": "Outbreak Review"})

        m_client.return_value.start_case.assert_called_once_with("Outbreak Review")
        self.assertEqual(m_emit.call_args_list[0].kwargs["what_action"], "rhinal_start_case")
        self.assertIn("Outbreak Review", response)

    def test_start_case_empty_title_asks_for_clarification_without_writing(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client:
            response = handle_rhinal_other("rhinal_start_case", "start a case", {"rhinal_text": ""})
        m_client.assert_not_called()
        self.assertIn("call the new case", response)

    def test_tag_prediction_emits_two_records_with_notion_id_and_confidence(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.tag_prediction.return_value = {"id": "pred-1"}
            response = handle_rhinal_other(
                "rhinal_tag_prediction", "tag record abc as a prediction with 80 percent confidence",
                {"notion_id": "abc", "confidence": 80})

        m_client.return_value.tag_prediction.assert_called_once_with("abc", 80)
        self.assertEqual(m_emit.call_args_list[0].kwargs["what_action"], "rhinal_tag_prediction")
        self.assertIn("80%", response)

    def test_resolve_prediction_emits_two_records_with_notion_id_and_outcome(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.resolve_prediction.return_value = {"calibrationScore": 80}
            response = handle_rhinal_other(
                "rhinal_resolve_prediction", "resolve prediction abc as correct",
                {"notion_id": "abc", "outcome": "correct"})

        m_client.return_value.resolve_prediction.assert_called_once_with("abc", "correct")
        self.assertEqual(m_emit.call_args_list[0].kwargs["what_action"], "rhinal_resolve_prediction")
        self.assertIn("correct", response)

    def test_configuration_failure_blocks_the_write_before_touching_the_client(self):
        from AgentCore.secure_key import KeyConfigurationError
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log",
                        side_effect=KeyConfigurationError("no key")), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action") as m_emit:
            response = handle_rhinal_other(
                "rhinal_decision_log", "log this decision: X", {"rhinal_text": "X"})

        m_client.return_value.decision_log.assert_not_called()
        m_emit.assert_not_called()
        self.assertIn("audit trail isn't configured", response)

    def test_call_error_is_audited_with_failure_outcome_and_surfaced_honestly(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.start_case.side_effect = RhinalCallError("unreachable")
            response = handle_rhinal_other("rhinal_start_case", "start a case: X", {"rhinal_text": "X"})

        self.assertEqual(m_emit.call_args_list[1].kwargs["outcome_status"], "failed")
        self.assertFalse(m_emit.call_args_list[1].kwargs["outcome_ok"])
        self.assertIn("Couldn't reach Rhinal", response)

    def test_unknown_handler_raises_rather_than_silently_succeeding(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient"):
            with self.assertRaises(ValueError):
                handle_rhinal_other("rhinal_attach_file", "x", {})


class TestAgainstTheRealAuditLog(unittest.TestCase):
    """Mocks nothing on the audit side for one representative write-capable
    tool -- runs the real AppendOnlyAuditLog (redirected by conftest.py's
    autouse fixture) and reads the actual records back, same convention
    test_rhinal_capture_audit_wiring.py established. Argument assertions
    alone cannot catch a record the storage engine rejects or mangles."""

    def test_start_case_writes_two_real_hmac_chained_records(self):
        from AgentCore.audit_trail import get_clinical_audit_log

        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client:
            m_client.return_value.start_case.return_value = {"id": "case-1"}
            handle_rhinal_other(
                "rhinal_start_case", "start a case: Outbreak Review", {"rhinal_text": "Outbreak Review"})

        log = get_clinical_audit_log()
        entries = log.get_entries(limit=10)
        self.assertEqual(len(entries), 2)

        attempted, completed = entries
        for entry in (attempted, completed):
            self.assertEqual(entry["what"], {
                "adapter": "rhinal_mcp", "action": "rhinal_start_case", "target": "rhinal_vault",
            })
            self.assertEqual(entry["source"], "voice")
        self.assertEqual(attempted["outcome"]["status"], "attempted")
        self.assertEqual(completed["outcome"]["status"], "success")
        self.assertLess(attempted["seq"], completed["seq"])
        self.assertEqual(completed["prev_hmac"], attempted["hmac"])
        self.assertTrue(log.verify_integrity())


if __name__ == "__main__":
    unittest.main()
