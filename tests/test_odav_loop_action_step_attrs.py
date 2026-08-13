"""
Live smoke-test finding: AgentCore/odav_loop.py's DECIDE/ACT phases read
step.action on plan steps, but the real dataclass (AgentCore/
intent_planner.py's ActionStep, and its ExecutionStep subclass) only
exposes .action_type (an ActionType enum) -- UIExecutor.execute_step()
right next to it already gets this correct. Any real "action" command
that reached the generic OBSERVE/DECIDE/ACT pipeline (not the adapter-
resolved fast path) crashed at the first DECIDE-phase print with
AttributeError, caught by execute()'s broad except and reported as a
generic "Execution error" -- reproduced live via voice ("open warfare").

A second, same-class bug: the ACT/VERIFY loop checked result.success,
but UIExecutor.execute_step() returns ui_executor.ExecutionResult, whose
field is .ok (a computed property), not .success -- also reproduced live
once the first bug was fixed and execution reached this line.
"""
import unittest
from unittest import mock

from AgentCore.intent_planner import ActionPlan, ActionStep, ActionType
from AgentCore.odav_loop import ODAVLoop, ODAVPhase
from AgentCore.ui_executor import ExecutionResult, ExecutionStatus


class TestCreateSimplePlanUsesActionType(unittest.TestCase):
    def test_open_app_step_has_no_action_attribute(self):
        loop = ODAVLoop()
        plan = loop._create_simple_plan("open notepad")

        self.assertEqual(len(plan.steps), 1)
        step = plan.steps[0]
        self.assertFalse(hasattr(step, "action"))
        self.assertEqual(step.action_type, ActionType.OPEN_APP)
        self.assertEqual(step.target, "notepad")


class TestExecuteFallbackUsesOkNotSuccess(unittest.TestCase):
    def test_open_app_fallback_returns_ok_true(self):
        loop = ODAVLoop()
        step = ActionStep(step_id=0, action_type=ActionType.OPEN_APP, target="notepad")

        with mock.patch("subprocess.Popen") as mock_popen, mock.patch("time.sleep"):
            result = loop._execute_fallback(step)

        mock_popen.assert_called_once()
        self.assertTrue(hasattr(result, "ok"))
        self.assertFalse(hasattr(result, "success"))
        self.assertTrue(result.ok)

    def test_unsupported_action_returns_ok_false(self):
        loop = ODAVLoop()
        step = ActionStep(step_id=0, action_type=ActionType.SCREENSHOT, target="x")

        result = loop._execute_fallback(step)

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Action not supported in fallback")


class TestExecuteDecideActVerifyPipeline(unittest.TestCase):
    """
    Drives ODAVLoop.execute() through the real DECIDE-phase print (the
    exact line that raised AttributeError live) and the real ACT/VERIFY
    result.ok check, with a real ActionStep/ExecutionResult pair and
    everything else around them mocked out (router/inspector/executor),
    matching this project's established "exercise the real objects the
    bug lives in, mock only the environment" convention.
    """

    def _loop_with_mocks(self, execute_step_result):
        loop = ODAVLoop()
        loop._planner = mock.Mock()
        loop._planner.plan.return_value = ActionPlan(
            plan_id="test",
            intent_text="open notepad",
            steps=[ActionStep(step_id=0, action_type=ActionType.OPEN_APP, target="notepad")],
        )
        loop._inspector = mock.Mock()
        loop._inspector.get_current_state.return_value = {"active_window": "test", "elements": []}
        loop._executor = mock.Mock()
        loop._executor.execute_step.return_value = execute_step_result
        loop._router = mock.Mock()
        loop._router.classify.return_value = mock.Mock(
            handler="action", extracted_entities={}
        )
        loop._recovery = None
        loop._reflection = None
        return loop

    def test_successful_step_reaches_verify_without_attribute_error(self):
        loop = self._loop_with_mocks(
            ExecutionResult(status=ExecutionStatus.SUCCESS, step_id=0, action_type="open_app")
        )

        result = loop.execute("open notepad")

        self.assertTrue(result.success, msg=result.message)
        self.assertNotIn("has no attribute", result.message)
        self.assertEqual(result.phase_reached, ODAVPhase.VERIFY)
        self.assertEqual(result.steps_executed, 1)

    def test_failed_step_with_no_reflection_reports_failure_without_crash(self):
        loop = self._loop_with_mocks(
            ExecutionResult(
                status=ExecutionStatus.FAILED, step_id=0, action_type="open_app",
                error="'warfare' is not recognized as an internal or external command",
            )
        )

        result = loop.execute("open warfare")

        self.assertFalse(result.success)
        self.assertNotIn("has no attribute", result.message)
        self.assertIn("warfare", result.message.lower())


if __name__ == "__main__":
    unittest.main()
