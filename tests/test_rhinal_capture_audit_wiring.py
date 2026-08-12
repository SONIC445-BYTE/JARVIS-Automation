"""
DEC-002 / D15: audit coverage for rhinal_capture -- the one real gap D15
found (code_engine is confirmed intentional build/dev infrastructure and
is deliberately NOT covered here).

Same structure and discipline as tests/test_ui_executor_audit_wiring.py,
because the failure model is the same one:

1. Configuration-class (audit key can't resolve) -- checked BEFORE the
   vault write, genuinely blocks it. The RHINAL client is never
   constructed and nothing goes on the wire. For an external,
   network-crossing write this is the whole point: an unauditable write
   to a third party must not happen at all.
2. Transient (audit write fails once the log is already resolvable) --
   the vault write still runs, its real result is returned, and the
   failure is folded into the physician-facing response rather than
   silently lost.

Plus one thing UIExecutor's wiring does not have and this does: two
records per write ("attempted" before the call, outcome after). The
ordering is asserted directly, since the entire value of the pre-record
is that it exists before anything leaves the machine.

These call the real jarvis.handle_rhinal_capture() and the real
AgentCore.mcp_audit -- no mirrored copy of either. Only the outermost
edges are mocked: the RHINAL client (a live network write) and, where
the test is about audit failure, the audit emission itself.
"""
import unittest
from unittest import mock

from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError
from AgentCore.secure_key import KeyConfigurationError
from jarvis import handle_rhinal_capture


UTTERANCE = "remember that the vendor meeting moved to Thursday"
THOUGHT = "the vendor meeting moved to Thursday"


def _ok_audit():
    return mock.Mock(ok=True, error=None, queued_to_fallback=False)


class TestSuccessfulCaptureIsAudited(unittest.TestCase):
    def test_two_records_are_emitted_with_the_deliberate_field_values(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertEqual(response, "Saved that to your Rhinal vault.")
        self.assertEqual(m_emit.call_count, 2)

        attempted = m_emit.call_args_list[0].kwargs
        completed = m_emit.call_args_list[1].kwargs

        for kwargs in (attempted, completed):
            # what: an MCP tool call to an external service, named so a
            # reader cannot mistake it for a GUI adapter driving a window.
            self.assertEqual(kwargs["what_adapter"], "rhinal_mcp")
            self.assertEqual(kwargs["what_action"], "rhinal_capture")
            self.assertEqual(kwargs["what_target"], "rhinal_vault")
            # why: the physician's actual words for this turn.
            self.assertEqual(kwargs["why"], UTTERANCE)
            # source: passed explicitly, not defaulted -- this call site
            # is only reachable from the mic-driven conversation loop.
            self.assertEqual(kwargs["source"], "voice")

        self.assertEqual(attempted["outcome_status"], "attempted")
        # None, not False -- the outcome is genuinely unknown at that point.
        self.assertIsNone(attempted["outcome_ok"])
        self.assertEqual(completed["outcome_status"], "success")
        self.assertTrue(completed["outcome_ok"])

    def test_the_attempted_record_is_written_before_anything_goes_on_the_wire(self):
        # The reason the pre-record exists at all: if the process dies
        # mid-call, the vault may still have the content. Order is the
        # property under test, so it is asserted directly.
        order = []

        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action") as m_emit:
            m_emit.side_effect = lambda **kw: (order.append(kw["outcome_status"]), _ok_audit())[1]
            m_client.return_value.capture.side_effect = lambda *a, **k: (
                order.append("vault_write"), {"saved": True, "vaultWorthy": True}
            )[1]
            handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertEqual(order, ["attempted", "vault_write", "success"])

    def test_borderline_but_saved_response_is_unchanged_by_the_audit_wiring(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()):
            m_client.return_value.capture.return_value = {
                "saved": True, "vaultWorthy": False, "worthinessReason": "seems like idle chatter",
            }
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertIn("Saved that to your Rhinal vault", response)
        self.assertIn("borderline", response)


class TestConfigurationFailureBlocksTheVaultWrite(unittest.TestCase):
    def test_unresolvable_audit_key_blocks_the_write_and_never_touches_the_client(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log",
                        side_effect=KeyConfigurationError("no key")), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action") as m_emit:
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        # The real point: nothing went to the external vault.
        m_client.assert_not_called()
        m_emit.assert_not_called()
        self.assertIn("audit trail isn't configured", response)

    def test_unexpected_non_key_error_checking_the_log_does_not_block_the_write(self):
        # Distinguishes "we know this is a config failure" from "something
        # else went wrong looking at the log" -- only the former earns a
        # hard stop. Mirrors ui_executor's equivalent case.
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log",
                        side_effect=RuntimeError("something else")), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()):
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        m_client.return_value.capture.assert_called_once_with(THOUGHT)
        self.assertIn("Saved that to your Rhinal vault", response)


class TestTransientAuditFailureNeverBlocksTheVaultWrite(unittest.TestCase):
    def test_failed_audit_write_still_performs_the_capture_and_warns_out_loud(self):
        failed = mock.Mock(ok=False, error="disk full", queued_to_fallback=True)

        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=failed):
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        m_client.return_value.capture.assert_called_once_with(THOUGHT)
        self.assertIn("Saved that to your Rhinal vault", response)
        # Surfaced to the physician, not buried in a log file.
        self.assertIn("audit record", response.lower())
        self.assertIn("queued for retry", response)

    def test_audit_write_that_could_not_even_be_queued_is_flagged_more_urgently(self):
        failed = mock.Mock(ok=False, error="disk truly full", queued_to_fallback=False)

        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=failed):
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertIn("Saved that to your Rhinal vault", response)
        self.assertIn("urgent attention", response)

    def test_audit_emission_raising_outright_does_not_break_the_capture(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action",
                        side_effect=RuntimeError("audit module exploded")):
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        m_client.return_value.capture.assert_called_once_with(THOUGHT)
        self.assertIn("Saved that to your Rhinal vault", response)
        self.assertIn("audit module exploded", response)

    def test_no_warning_is_appended_when_the_audit_writes_succeed(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()):
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertEqual(response, "Saved that to your Rhinal vault.")


class TestFailedVaultWritesAreAuditedToo(unittest.TestCase):
    """
    A failed external write is a real event a compliance reader needs --
    and, per rhinal_mcp_client.py, a RhinalCallError does not even prove
    nothing landed remotely (an accepted-then-timed-out write is
    indistinguishable from a rejected one). Skipping the record because
    "it failed" would be the wrong call.
    """

    def test_call_error_is_audited_with_the_failure_outcome(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.capture.side_effect = RhinalCallError(
                "Rhinal reported an error for rhinal_capture: Error: Missing modelId"
            )
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertEqual(m_emit.call_count, 2)
        completed = m_emit.call_args_list[1].kwargs
        self.assertEqual(completed["outcome_status"], "failed")
        self.assertFalse(completed["outcome_ok"])
        self.assertIn("Missing modelId", completed["outcome_error"])
        # The physician-facing message is unchanged from before the wiring.
        self.assertIn("Couldn't reach Rhinal", response)

    def test_config_error_from_the_client_is_audited_and_reported_distinctly(self):
        # RhinalConfigError ("Rhinal isn't configured") is raised before
        # any network call, so nothing actually left the machine -- but
        # the attempted/failed pair reads accurately for that too, and
        # the specific message must still reach the physician rather than
        # being flattened into a generic failure.
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.capture.side_effect = RhinalConfigError(
                "Rhinal isn't configured -- missing environment variable(s): RHINAL_API_KEY"
            )
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertEqual(m_emit.call_count, 2)
        self.assertEqual(m_emit.call_args_list[1].kwargs["outcome_status"], "failed")
        self.assertIn("RHINAL_API_KEY", response)

    def test_an_unexpected_exception_type_is_never_reported_as_a_save(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=_ok_audit()) as m_emit:
            m_client.return_value.capture.side_effect = ValueError("totally unexpected")
            response = handle_rhinal_capture(UTTERANCE, THOUGHT)

        self.assertEqual(m_emit.call_args_list[1].kwargs["outcome_status"], "failed")
        self.assertNotIn("Saved that", response)
        self.assertIn("totally unexpected", response)


class TestNonActionsAreNotAudited(unittest.TestCase):
    def test_empty_capture_text_emits_nothing_and_calls_nothing(self):
        # A clarification prompt is not an action. Logging non-events
        # devalues a log whose worth depends on every line being real.
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client, \
             mock.patch("AgentCore.audit_trail.get_clinical_audit_log") as m_get, \
             mock.patch("AgentCore.audit_trail.emit_clinical_action") as m_emit:
            response = handle_rhinal_capture("remember that", "")

        m_client.assert_not_called()
        m_get.assert_not_called()
        m_emit.assert_not_called()
        self.assertIn("didn't catch", response)


class TestAgainstTheRealAuditLog(unittest.TestCase):
    """
    Everything above mocks emit_clinical_action to assert on arguments.
    This one mocks nothing on the audit side: it runs the real
    AppendOnlyAuditLog (redirected to a temp dir with a real key by the
    autouse fixture in conftest.py) and reads back what actually landed
    on disk, including the HMAC chain. Argument assertions cannot catch a
    record that the storage engine rejects or mangles.
    """

    def test_the_real_records_carry_all_six_dec002_fields_and_verify(self):
        from AgentCore.audit_trail import get_clinical_audit_log

        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as m_client:
            m_client.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            handle_rhinal_capture(UTTERANCE, THOUGHT)

        log = get_clinical_audit_log()
        entries = log.get_entries(limit=10)
        self.assertEqual(len(entries), 2)

        attempted, completed = entries
        for entry in (attempted, completed):
            self.assertTrue(entry["who"])                      # who
            self.assertEqual(entry["what"], {                  # what
                "adapter": "rhinal_mcp",
                "action": "rhinal_capture",
                "target": "rhinal_vault",
            })
            self.assertIn("ts", entry)                         # when
            self.assertEqual(entry["why"], UTTERANCE)          # why
            self.assertEqual(entry["source"], "voice")         # source
            self.assertEqual(entry["consent"], "direct_user_action")  # consent

        self.assertEqual(attempted["outcome"]["status"], "attempted")
        self.assertEqual(completed["outcome"]["status"], "success")
        # The pre-record really is first in the chain, and the chain is intact.
        self.assertLess(attempted["seq"], completed["seq"])
        self.assertEqual(completed["prev_hmac"], attempted["hmac"])
        self.assertTrue(log.verify_integrity())


if __name__ == "__main__":
    unittest.main()
