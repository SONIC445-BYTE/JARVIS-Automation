"""
DEC-002: UIExecutor.execute_intent() as the single pre-adapter audit
chokepoint. Two failure modes tested separately, matching the
instructed distinction:

1. Configuration-class (audit key can't resolve) -- checked BEFORE the
   action runs, genuinely blocks it (returns FAILED, adapter never
   invoked). An earlier draft checked this *after* running the action,
   which would have meant the action already happened by the time the
   "stop" fired -- caught and fixed before shipping, tested here so it
   can't regress.
2. Transient (audit write fails once the log is already resolvable) --
   the action still runs and its real result is returned; the failure
   is folded into result.metadata['audit_write_warning'] rather than
   silently lost, and ODAVLoop surfaces it into the physician-facing
   message.
"""
import unittest
from unittest import mock

from AgentCore.ui_executor import UIExecutor, ExecutionResult, ExecutionStatus
from AgentCore.secure_key import KeyConfigurationError
from daemon.intent_parser import Intent


class _FakeAdapter:
    def supports(self, action):
        return action == "open_app"

    def open_app(self):
        return True


class TestConfigurationFailureBlocksBeforeAction(unittest.TestCase):
    def test_key_configuration_failure_returns_failed_without_invoking_the_adapter(self):
        executor = UIExecutor.__new__(UIExecutor)
        executor._adapters = {"notepad": _FakeAdapter()}
        adapter = executor._adapters["notepad"]
        adapter.open_app = mock.Mock(return_value=True)

        intent = Intent(adapter="notepad", action="open_app", target="notepad", source_text="open notepad")

        with mock.patch("AgentCore.audit_trail.get_clinical_audit_log", side_effect=KeyConfigurationError("no key")):
            result = executor.execute_intent(intent)

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("audit trail isn't configured", result.error)
        adapter.open_app.assert_not_called()  # the real point: action never ran

    def test_unexpected_non_key_error_checking_audit_log_does_not_block_the_action(self):
        # Distinguishes "we know this is a config failure" from "some
        # other unexpected error occurred checking the log" -- only the
        # former is treated as the hard stop.
        executor = UIExecutor.__new__(UIExecutor)
        executor._adapters = {"notepad": _FakeAdapter()}
        adapter = executor._adapters["notepad"]
        adapter.open_app = mock.Mock(return_value=True)

        intent = Intent(adapter="notepad", action="open_app", target="notepad", source_text="open notepad")

        with mock.patch("AgentCore.audit_trail.get_clinical_audit_log", side_effect=RuntimeError("something else")), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=mock.Mock(ok=True)):
            result = executor.execute_intent(intent)

        adapter.open_app.assert_called_once()
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)


class TestTransientAuditFailureNeverBlocksTheAction(unittest.TestCase):
    def test_audit_write_failure_still_returns_the_real_action_result(self):
        executor = UIExecutor.__new__(UIExecutor)
        executor._adapters = {"notepad": _FakeAdapter()}
        adapter = executor._adapters["notepad"]
        adapter.open_app = mock.Mock(return_value=True)

        intent = Intent(adapter="notepad", action="open_app", target="notepad", source_text="open notepad")

        fake_audit_result = mock.Mock(ok=False, error="disk full", queued_to_fallback=True)
        with mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=fake_audit_result):
            result = executor.execute_intent(intent)

        adapter.open_app.assert_called_once()
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)  # the real action succeeded
        self.assertIn("audit_write_warning", result.metadata)
        self.assertIn("queued for retry", result.metadata["audit_write_warning"])

    def test_successful_audit_write_adds_no_warning(self):
        executor = UIExecutor.__new__(UIExecutor)
        executor._adapters = {"notepad": _FakeAdapter()}
        adapter = executor._adapters["notepad"]
        adapter.open_app = mock.Mock(return_value=True)

        intent = Intent(adapter="notepad", action="open_app", target="notepad", source_text="open notepad")

        fake_audit_result = mock.Mock(ok=True)
        with mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=fake_audit_result):
            result = executor.execute_intent(intent)

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertNotIn("audit_write_warning", result.metadata)


class TestAuditRecordContent(unittest.TestCase):
    def test_emit_clinical_action_called_with_intent_fields(self):
        executor = UIExecutor.__new__(UIExecutor)
        executor._adapters = {"notepad": _FakeAdapter()}
        adapter = executor._adapters["notepad"]
        adapter.open_app = mock.Mock(return_value=True)

        intent = Intent(adapter="notepad", action="open_app", target="notepad", source_text="open notepad please")

        with mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=mock.Mock(ok=True)) as m_emit:
            executor.execute_intent(intent)

        m_emit.assert_called_once()
        _, kwargs = m_emit.call_args
        self.assertEqual(kwargs["what_adapter"], "notepad")
        self.assertEqual(kwargs["what_action"], "open_app")
        self.assertEqual(kwargs["what_target"], "notepad")
        self.assertEqual(kwargs["why"], "open notepad please")
        self.assertEqual(kwargs["outcome_ok"], True)


class TestBlockedActionsAreAuditedToo(unittest.TestCase):
    """
    execute_intent() calls _emit_audit_for_intent() unconditionally on
    whatever ExecutionResult _execute_intent_inner() returns -- it does
    not branch on status. Worth locking in explicitly: a BLOCKED result
    (CAPTCHA/login-wall pause, see platform_adapters.browser_automation.
    BlockedError) is a real attempted action for compliance purposes,
    not a no-op, so it must reach the audit log the same as SUCCESS/
    FAILED, not be silently skipped because it isn't a "normal" outcome.
    """

    def test_blocked_result_still_gets_an_audit_record(self):
        executor = UIExecutor.__new__(UIExecutor)

        class _BlockedAdapter:
            def supports(self, action):
                return action == "send_message"

            def send_message(self, target, message):
                from platform_adapters.browser_automation import BlockedError
                raise BlockedError("Login wall detected -- complete sign-in manually.")

        executor._adapters = {"whatsapp_web": _BlockedAdapter()}
        intent = Intent(
            adapter="whatsapp_web", action="send_message", target="Alice",
            source_text="message alice on whatsapp web saying hi",
        )

        with mock.patch("AgentCore.audit_trail.get_clinical_audit_log", return_value=mock.Mock()), \
             mock.patch("AgentCore.audit_trail.emit_clinical_action", return_value=mock.Mock(ok=True)) as m_emit:
            result = executor.execute_intent(intent)

        self.assertEqual(result.status, ExecutionStatus.BLOCKED)
        m_emit.assert_called_once()
        _, kwargs = m_emit.call_args
        self.assertEqual(kwargs["outcome_status"], "blocked")
        self.assertEqual(kwargs["what_adapter"], "whatsapp_web")


if __name__ == "__main__":
    unittest.main()
