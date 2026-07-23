"""
Phase D: the approval-gated apply confirmation flow, exercised through
PersistentWakeService's actual pending-apply turn-handling method (not
just Level6Coordinator.apply() in isolation) -- this is the real
conversation-loop code path jarvis.py --convo uses. Mirrors
tests/test_install_confirmation_flow.py's pattern for the analogous
Phase 2c gate.

LEVEL6_ENGINE.apply() is mocked in every test so these never write to a
real directory, regardless of what's on the machine running them.
"""
import unittest
from unittest import mock

import jarvis
from AgentCore.level6.orchestrator import PendingLevel6Apply


class TestLevel6ApplyConfirmationFlow(unittest.TestCase):
    def setUp(self):
        self.service = jarvis.PersistentWakeService(conversation_mode=True)

    def _pending(self):
        return PendingLevel6Apply(
            request_id="req1",
            plan=[{"type": "create_file", "target": "add.py"}],
            sandbox_dir="/fake/sandbox",
            target_dir="/fake/target",
            explain="Add a helper function",
            risk_score=0.1,
        )

    def test_decline_never_calls_apply(self):
        self.service._pending_level6_apply = self._pending()
        with mock.patch("jarvis.LEVEL6_ENGINE", create=True) as mock_engine:
            response = self.service._handle_level6_apply_confirmation("no thanks")
        mock_engine.apply.assert_not_called()
        self.assertIsNone(self.service._pending_level6_apply)
        self.assertIn("won't apply", response)

    def test_ambiguous_reply_treated_as_decline(self):
        self.service._pending_level6_apply = self._pending()
        with mock.patch("jarvis.LEVEL6_ENGINE", create=True) as mock_engine:
            response = self.service._handle_level6_apply_confirmation("what do you mean")
        mock_engine.apply.assert_not_called()
        self.assertIn("won't apply", response)

    def test_affirmative_calls_apply_and_reports_success(self):
        self.service._pending_level6_apply = self._pending()
        with mock.patch("jarvis.LEVEL6_ENGINE", create=True) as mock_engine:
            mock_engine.apply.return_value = {"status": "applied", "files": ["/fake/target/add.py"]}
            response = self.service._handle_level6_apply_confirmation("yes")
        mock_engine.apply.assert_called_once()
        self.assertIsNone(self.service._pending_level6_apply)
        self.assertIn("Applied", response)
        self.assertIn("add.py", response)

    def test_affirmative_reports_failed_and_reverted_honestly(self):
        self.service._pending_level6_apply = self._pending()
        with mock.patch("jarvis.LEVEL6_ENGINE", create=True) as mock_engine:
            mock_engine.apply.return_value = {
                "status": "apply_failed",
                "reason": "missing file",
                "reverted": True,
            }
            response = self.service._handle_level6_apply_confirmation("yes, go ahead")
        self.assertIn("failed", response.lower())
        self.assertIn("reverted", response.lower())
        self.assertIn("missing file", response)

    def test_pending_state_always_cleared_regardless_of_reply(self):
        for reply in ("yes", "no", "maybe", "apply it"):
            self.service._pending_level6_apply = self._pending()
            with mock.patch("jarvis.LEVEL6_ENGINE", create=True) as mock_engine:
                mock_engine.apply.return_value = {"status": "applied", "files": []}
                self.service._handle_level6_apply_confirmation(reply)
            self.assertIsNone(self.service._pending_level6_apply)


if __name__ == "__main__":
    unittest.main()
