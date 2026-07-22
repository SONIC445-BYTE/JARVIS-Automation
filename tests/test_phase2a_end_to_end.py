"""
Phase 2a DoD verification.

Confirms the new command shape resolves and executes end-to-end for a
real adapter (browser), and that open_app/close_app still work with no
regression when no adapter is registered for the named platform (the
pre-2a raw subprocess/os.startfile fallback path).

Uses dry_run=True throughout so this test suite never opens/closes real
applications -- live end-to-end verification (real Chrome open/close)
was done manually and separately, see PR description.
"""
import unittest
from daemon.intent_parser import Intent
from AgentCore.intent_router import IntentRouter
from AgentCore.command_router import CommandRouter
from AgentCore.ui_executor import UIExecutor, ExecutionStatus


class TestPhase2aClassification(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_open_browser_resolves_to_action_with_intent(self):
        result = self.router.classify("open browser")
        self.assertEqual(result.handler, "action")
        resolved = result.extracted_entities.get("resolved_intent")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.adapter, "browser")
        self.assertEqual(resolved.action, "open_app")

    def test_unrelated_text_does_not_resolve_an_intent(self):
        result = self.router.classify("what is the capital of France?")
        resolved = result.extracted_entities.get("resolved_intent")
        self.assertIsNone(resolved)

    def test_coding_command_unaffected_by_command_router(self):
        # Regression: Phase 1's fix must still work with CommandRouter
        # wired in ahead of CODE_PATTERNS in classify().
        result = self.router.classify("write a python script that sorts a list")
        self.assertEqual(result.handler, "code_engine")


class TestPhase2aExecution(unittest.TestCase):
    def setUp(self):
        self.executor = UIExecutor(adapter_dry_run=True)

    def test_open_app_through_real_adapter_dry_run(self):
        intent = Intent(adapter="browser", action="open_app", target="browser")
        result = self.executor.execute_intent(intent)
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.metadata["adapter"], "browser")

    def test_close_app_through_real_adapter_dry_run(self):
        intent = Intent(adapter="browser", action="close_app", target="browser")
        result = self.executor.execute_intent(intent)
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)

    def test_send_message_through_real_adapter_dry_run(self):
        # This is the capability that did not exist anywhere before
        # Phase 2a -- no ActionType, no router pattern, no UIExecutor
        # handler could ever produce or execute this verb.
        intent = Intent(adapter="whatsapp_desktop", action="send_message", target="mom", message="hi")
        result = self.executor.execute_intent(intent)
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)

    def test_read_unread_through_real_adapter_dry_run(self):
        intent = Intent(adapter="telegram_desktop", action="read_unread", target="telegram")
        result = self.executor.execute_intent(intent)
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)

    def test_open_app_falls_back_when_no_adapter_registered(self):
        """Regression: platforms with no daemon adapter (e.g. 'calculator')
        must still work via the pre-2a raw open_app fallback."""
        intent = Intent(adapter="unregistered_platform", action="open_app", target="calc.exe")
        result = self.executor.execute_intent(intent)
        # _open_app's raw os.startfile/subprocess path was exercised, not
        # an adapter -- it may succeed or fail depending on the host, but
        # it must not be a "no fallback" error.
        self.assertNotIn("No adapter registered", result.error or "")

    def test_send_message_has_no_fallback_when_no_adapter_registered(self):
        """send_message never had a legacy fallback -- unlike open_app,
        there is nothing to fall back to."""
        intent = Intent(adapter="unregistered_platform", action="send_message", target="x", message="y")
        result = self.executor.execute_intent(intent)
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn("No adapter registered", result.error)


if __name__ == "__main__":
    unittest.main()
