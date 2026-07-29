"""
RHINAL MCP integration -- jarvis.py's conversation-loop dispatch branch
(`elif intent.handler == "rhinal_capture":`).

Same "mirror the exact dispatch code" approach as
test_pending_resume_flow.py's TestActionHandlerSetsAndReplacesPendingResume
-- the branch lives inside _conversation_loop's large method body, not a
separately callable unit, so these tests replicate its exact shape
(documented so a change there must update this mirror, same discipline
as the existing precedent) rather than mocking mic/audio to exercise the
real loop.
"""
import unittest
from unittest import mock

from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError


def _run_rhinal_capture_branch(capture_text):
    # Mirrors jarvis.py's `elif intent.handler == "rhinal_capture":`
    # branch exactly -- see jarvis.py for the real code this pins.
    if not capture_text:
        return "I didn't catch what you wanted me to remember -- try 'remember that ...' with the thought included."

    from AgentCore.rhinal_mcp_client import RhinalMCPClient
    try:
        rhinal_result = RhinalMCPClient().capture(capture_text)
        response = "Saved that to your Rhinal vault."
        if rhinal_result.get("vaultWorthy") is False:
            reason = rhinal_result.get("worthinessReason")
            response += f" (Rhinal's classifier flagged it as borderline{': ' + reason if reason else ''}, but saved it anyway.)"
        return response
    except RhinalConfigError as e:
        return str(e)
    except RhinalCallError as e:
        return f"Couldn't reach Rhinal to save that: {e}"


class TestRhinalCaptureDispatch(unittest.TestCase):
    def test_empty_capture_text_gives_honest_clarification_without_calling_client(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as mock_client_cls:
            response = _run_rhinal_capture_branch("")
        self.assertIn("didn't catch", response)
        mock_client_cls.assert_not_called()

    def test_successful_capture_reports_saved(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as mock_client_cls:
            mock_client_cls.return_value.capture.return_value = {"saved": True, "vaultWorthy": True}
            response = _run_rhinal_capture_branch("the vendor meeting moved to Thursday")
        self.assertEqual(response, "Saved that to your Rhinal vault.")

    def test_successful_but_borderline_capture_still_reports_saved_with_a_note(self):
        # capture() saves unconditionally once it completes (verified
        # against RHINAL's own tools.ts) -- vaultWorthy=False must NOT
        # be reported as "not saved".
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as mock_client_cls:
            mock_client_cls.return_value.capture.return_value = {
                "saved": True, "vaultWorthy": False, "worthinessReason": "seems like idle chatter",
            }
            response = _run_rhinal_capture_branch("just thinking out loud")
        self.assertIn("Saved that to your Rhinal vault", response)
        self.assertIn("borderline", response)
        self.assertIn("seems like idle chatter", response)

    def test_config_error_surfaces_the_specific_missing_env_var_message(self):
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as mock_client_cls:
            mock_client_cls.return_value.capture.side_effect = RhinalConfigError(
                "Rhinal isn't configured -- missing environment variable(s): RHINAL_MODEL_ID"
            )
            response = _run_rhinal_capture_branch("a thought")
        self.assertIn("RHINAL_MODEL_ID", response)

    def test_call_error_surfaces_as_honest_could_not_reach_message(self):
        # The exact honest-failure shape confirmed live this round:
        # the real server reachable, real handshake succeeded, but the
        # tool call itself failed (rhk_ key's account needs an explicit
        # modelId) -- never reported as a fake success.
        with mock.patch("AgentCore.rhinal_mcp_client.RhinalMCPClient") as mock_client_cls:
            mock_client_cls.return_value.capture.side_effect = RhinalCallError(
                "Rhinal reported an error for rhinal_capture: Error: Missing modelId"
            )
            response = _run_rhinal_capture_branch("a thought")
        self.assertIn("Couldn't reach Rhinal", response)
        self.assertIn("Missing modelId", response)


if __name__ == "__main__":
    unittest.main()
