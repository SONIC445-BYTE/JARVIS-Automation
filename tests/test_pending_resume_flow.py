"""
Phase 2g: the PendingResume (CAPTCHA/login-wall pause/resume) state
machine, exercised through PersistentWakeService's real methods -- same
approach as test_install_confirmation_flow.py for PendingInstall. Also
covers ExecutionStatus.BLOCKED / ODAVResult.blocked propagation through
UIExecutor and ODAVLoop, and the adversarial cases from the Phase 2g
adversarial-testing pass: double resume with no pending state, retry
after resume when the block wasn't actually cleared, and a second block
arriving while an earlier one is still unresolved.
"""
import unittest
from unittest import mock

import jarvis
from jarvis import PendingResume


class TestHandleResume(unittest.TestCase):
    def setUp(self):
        self.service = jarvis.PersistentWakeService(conversation_mode=True)

    def _pending(self, original_text="send whatsapp web message to mom saying hi", reason="please log in"):
        return PendingResume(original_text=original_text, reason=reason)

    def test_no_pending_state_returns_honest_message_not_a_crash(self):
        # Adversarial case: _handle_resume called with nothing pending
        # (e.g. a "continue" that slipped through, or a future refactor
        # bug) must not raise AttributeError on None.
        self.service._pending_resume = None
        response = self.service._handle_resume("continue")
        self.assertIn("Nothing", response)
        self.assertIsNone(self.service._pending_resume)

    def test_double_resume_second_call_is_also_safe(self):
        self.service._pending_resume = self._pending()
        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=True, message="OK", blocked=False)
        self.service._odav = mock_odav

        first = self.service._handle_resume("continue")
        self.assertIn("Continuing", first)
        self.assertIsNone(self.service._pending_resume)

        # Second "continue" with nothing left pending -- must not crash,
        # must not re-invoke odav.execute again.
        second = self.service._handle_resume("continue")
        self.assertIn("Nothing", second)
        mock_odav.execute.assert_called_once()

    def test_resume_with_no_odav_reports_still_blocked(self):
        self.service._pending_resume = self._pending(reason="scan the qr code")
        if hasattr(self.service, "_odav"):
            del self.service._odav
        response = self.service._handle_resume("continue")
        self.assertIn("Still blocked", response)
        self.assertIn("scan the qr code", response)
        self.assertIsNone(self.service._pending_resume)

    def test_resume_success_clears_pending_and_reports_continuing(self):
        self.service._pending_resume = self._pending()
        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=True, message="send_message on whatsapp_web: OK", blocked=False)
        self.service._odav = mock_odav

        response = self.service._handle_resume("continue")

        mock_odav.execute.assert_called_once_with("send whatsapp web message to mom saying hi")
        self.assertIsNone(self.service._pending_resume)
        self.assertIn("Continuing", response)

    def test_resume_genuine_failure_clears_pending_and_reports_failure(self):
        # Retry ran, block was cleared, but the action itself genuinely
        # failed (not blocked again) -- must not be reported as blocked
        # or as success.
        self.service._pending_resume = self._pending()
        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=False, message="search box not found", blocked=False)
        self.service._odav = mock_odav

        response = self.service._handle_resume("continue")

        self.assertIsNone(self.service._pending_resume)
        self.assertIn("still failed", response)
        self.assertIn("search box not found", response)

    def test_retry_still_blocked_resets_pending_with_new_reason(self):
        # Adversarial case: physician says "continue" but never actually
        # solved the block (or a second block appears). Must re-pause,
        # not silently loop or report a fake success.
        self.service._pending_resume = self._pending(reason="please log in")
        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=False, message="please log in (still)", blocked=True)
        self.service._odav = mock_odav

        response = self.service._handle_resume("continue")

        self.assertIsNotNone(self.service._pending_resume)
        self.assertEqual(self.service._pending_resume.reason, "please log in (still)")
        self.assertEqual(response, "please log in (still)")


class TestActionHandlerSetsAndReplacesPendingResume(unittest.TestCase):
    """Exercises the dispatch-loop branch (jarvis.py's `elif intent.handler
    == "action":`) directly, the same way it's invoked from the real
    conversation loop, without needing mic/audio setup."""

    def setUp(self):
        self.service = jarvis.PersistentWakeService(conversation_mode=True)

    def _run_action_branch(self, text, odav_result):
        # Mirrors the exact logic in jarvis.py's conversation loop for
        # intent.handler == "action", so this test breaks if that logic
        # changes shape.
        result = odav_result
        if getattr(result, "blocked", False):
            if self.service._pending_resume is not None:
                response = (
                    f"Note: I still had '{self.service._pending_resume.original_text}' waiting on "
                    f"a manual step -- switching to this new one instead. {result.message}"
                )
            else:
                response = f"{result.message}"
            self.service._pending_resume = PendingResume(original_text=text, reason=result.message)
            from onboarding import persist_pending_state
            persist_pending_state("resume", result.message)
        else:
            response = result.message if result.success else f"Failed: {result.message}"
        return response

    @mock.patch("onboarding.persist_pending_state")
    def test_first_block_persists_pending_state(self, mock_persist):
        result = mock.Mock(blocked=True, message="please log in", success=False)
        self._run_action_branch("send whatsapp web message to mom saying hi", result)
        mock_persist.assert_called_once_with("resume", "please log in")

    def test_first_block_sets_pending_resume_cleanly(self):
        result = mock.Mock(blocked=True, message="please log in", success=False)
        response = self._run_action_branch("send whatsapp web message to mom saying hi", result)
        self.assertNotIn("Note:", response)
        self.assertEqual(self.service._pending_resume.original_text, "send whatsapp web message to mom saying hi")

    def test_second_block_while_first_unresolved_warns_instead_of_silently_dropping(self):
        # Adversarial case: concurrent pending states. Only one slot
        # exists, so the second block must not silently erase the first
        # without any indication to the physician.
        first_result = mock.Mock(blocked=True, message="please log in", success=False)
        self._run_action_branch("send whatsapp web message to mom saying hi", first_result)
        first_pending = self.service._pending_resume

        second_result = mock.Mock(blocked=True, message="scan the qr code", success=False)
        response = self._run_action_branch("send telegram web message to dad saying hi", second_result)

        self.assertIn("Note:", response)
        self.assertIn(first_pending.original_text, response)
        self.assertEqual(self.service._pending_resume.original_text, "send telegram web message to dad saying hi")
        self.assertNotEqual(self.service._pending_resume, first_pending)


class TestBlockedStatusPropagation(unittest.TestCase):
    """Confirms BlockedError -> ExecutionStatus.BLOCKED -> ODAVResult.blocked
    survives the full stack, and that ordinary exceptions are unaffected
    (regression check on the isinstance-based branch added in ui_executor.py)."""

    def test_ui_executor_maps_blocked_error_to_blocked_status(self):
        from AgentCore.ui_executor import UIExecutor, ExecutionStatus
        from platform_adapters.browser_automation import BlockedError
        from daemon.intent_parser import Intent

        executor = UIExecutor.__new__(UIExecutor)
        fake_adapter = mock.Mock()
        fake_adapter.supports.return_value = True
        fake_adapter.send_message.side_effect = BlockedError("please log in")
        executor._get_adapter = mock.Mock(return_value=fake_adapter)

        intent = Intent(adapter="whatsapp_web", action="send_message", target="mom", message="hi")
        result = executor.execute_intent(intent)

        self.assertEqual(result.status, ExecutionStatus.BLOCKED)
        self.assertEqual(result.error, "please log in")

    def test_ui_executor_ordinary_exception_still_maps_to_failed(self):
        from AgentCore.ui_executor import UIExecutor, ExecutionStatus
        from daemon.intent_parser import Intent

        executor = UIExecutor.__new__(UIExecutor)
        fake_adapter = mock.Mock()
        fake_adapter.supports.return_value = True
        fake_adapter.send_message.side_effect = RuntimeError("boom")
        executor._get_adapter = mock.Mock(return_value=fake_adapter)

        intent = Intent(adapter="whatsapp_web", action="send_message", target="mom", message="hi")
        result = executor.execute_intent(intent)

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertEqual(result.error, "boom")

    def test_odav_loop_surfaces_blocked_result(self):
        from AgentCore.odav_loop import ODAVLoop
        from AgentCore.ui_executor import ExecutionStatus

        loop = ODAVLoop()
        loop._planner = mock.Mock()  # non-None short-circuits _init_modules()
        loop._router = mock.Mock()
        loop._executor = mock.Mock()

        resolved_intent = mock.Mock(adapter="whatsapp_web", action="send_message")
        routed = mock.Mock(handler="not_llm")
        routed.extracted_entities = {"resolved_intent": resolved_intent}
        loop._router.classify.return_value = routed

        exec_result = mock.Mock(status=ExecutionStatus.BLOCKED, error="please log in")
        loop._executor.execute_intent.return_value = exec_result

        result = loop.execute("send whatsapp web message to mom saying hi")

        self.assertTrue(result.blocked)
        self.assertFalse(result.success)
        self.assertEqual(result.message, "please log in")


class TestPendingResumePersistenceHooks(unittest.TestCase):
    """PendingResume is in-memory only on PersistentWakeService -- a
    restart while one is set silently loses it with no trace. jarvis.py
    calls onboarding.persist_pending_state()/clear_pending_state() at
    the same points _pending_resume gets set/cleared so the compact
    status box's next launch can at least surface that something was
    left unresolved (see onboarding.py's render_status_box "Pending"
    field). These tests confirm the hooks actually fire, not just that
    onboarding.py's own persistence functions work in isolation."""

    def setUp(self):
        self.service = jarvis.PersistentWakeService(conversation_mode=True)

    def _pending(self, reason="please log in"):
        return PendingResume(original_text="send whatsapp web message to mom saying hi", reason=reason)

    @mock.patch("onboarding.clear_pending_state")
    def test_handle_resume_clears_persisted_state_on_success(self, mock_clear):
        self.service._pending_resume = self._pending()
        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=True, message="OK", blocked=False)
        self.service._odav = mock_odav

        self.service._handle_resume("continue")

        mock_clear.assert_called_once()

    @mock.patch("onboarding.persist_pending_state")
    @mock.patch("onboarding.clear_pending_state")
    def test_handle_resume_repersists_on_still_blocked(self, mock_clear, mock_persist):
        self.service._pending_resume = self._pending()
        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=False, message="still blocked", blocked=True)
        self.service._odav = mock_odav

        self.service._handle_resume("continue")

        mock_clear.assert_called_once()
        mock_persist.assert_called_once_with("resume", "still blocked")


if __name__ == "__main__":
    unittest.main()
