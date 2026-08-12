"""
RHINAL MCP integration -- jarvis.py's conversation-loop dispatch branch
(`elif intent.handler == "rhinal_capture":`).

These used to *mirror* the branch's code in this file, because the branch
lived inside _conversation_loop's large method body with no separately
callable unit (the documented test_pending_resume_flow.py precedent). The
branch body has since been extracted to jarvis.handle_rhinal_capture(),
so these now call the real function -- the mirror is gone. That matters
more than tidiness here: DEC-002 audit coverage for an external vault
write must not be verified against a copy of the code that could pass
while the shipped branch is broken.

The audit wiring itself is covered separately in
tests/test_rhinal_capture_audit_wiring.py; these tests keep their
original job of pinning the physician-facing responses, which the audit
wiring must not have changed.
"""
import unittest
from unittest import mock

from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError
from jarvis import handle_rhinal_capture


def _run_rhinal_capture_branch(capture_text):
    # The real dispatch branch. `text` (the physician's whole utterance)
    # and capture_text (the extracted thought) are separate arguments in
    # the real code; these tests only care about capture_text, so the
    # utterance is synthesized from it.
    return handle_rhinal_capture(f"remember that {capture_text}", capture_text)


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
