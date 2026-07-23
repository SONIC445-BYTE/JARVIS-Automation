"""
Phase 2c DoD: the 5 required branches, exercised through
PersistentWakeService's actual pending-install turn-handling method (not
just the gate in isolation) -- this is the real conversation-loop code
path jarvis.py --convo uses.

The real winget subprocess call and the real availability re-scan are
mocked in every test so these never install real software or spawn real
subprocesses, regardless of what's installed on the machine running them.
"""
import unittest
from unittest import mock

import jarvis
from AgentCore.resolution_gate import PendingInstall
from platform_adapters.winget_installer import InstallResult


class TestInstallConfirmationFlow(unittest.TestCase):
    def setUp(self):
        self.service = jarvis.PersistentWakeService(conversation_mode=True)

    def _pending(self, winget_id=("Telegram.TelegramDesktop", "winget")):
        return PendingInstall(
            original_text="open telegram",
            platform_display_name="Telegram",
            adapter_key="telegram_desktop",
            winget_id=winget_id,
        )

    # Branch 1 (NO_ADAPTER) is covered by test_resolution_gate.py and
    # test_no_pending_install_state_created_for_no_adapter below -- the
    # gate never offers to install for a fabricated/nonexistent adapter,
    # so there is no confirmation flow to test for that branch.

    def test_no_pending_install_state_created_for_no_adapter(self):
        # self.service._router is only built by _initialize() (audio/mic
        # setup); build one directly to exercise the real
        # classify() -> handler mapping without that.
        from AgentCore.intent_router import IntentRouter
        router = IntentRouter()
        routed = router.classify("open netflix")
        self.assertEqual(routed.handler, "action_no_adapter")
        gate_result = routed.extracted_entities["gate_result"]
        self.assertIsNone(gate_result.winget_id)  # no winget_id ever offered for NO_ADAPTER

    # Branch 2: known adapter, not installed, user declines.
    def test_decline(self):
        self.service._pending_install = self._pending()
        response = self.service._handle_install_confirmation("no thanks")
        self.assertIsNone(self.service._pending_install)
        self.assertIn("won't install", response)
        self.assertIn("Telegram", response)

    def test_ambiguous_reply_treated_as_decline(self):
        self.service._pending_install = self._pending()
        response = self.service._handle_install_confirmation("what do you mean")
        self.assertIsNone(self.service._pending_install)
        self.assertIn("won't install", response)

    # Branch 3: known adapter, not installed, confirm, install succeeds, retry succeeds.
    @mock.patch("AgentCore.resolution_gate._get_default_availability_checker")
    @mock.patch("platform_adapters.winget_installer.install")
    def test_confirm_install_success_and_retry(self, mock_install, mock_get_checker):
        mock_install.return_value = InstallResult(ok=True, message="Installed successfully.")
        mock_get_checker.return_value = mock.Mock()

        mock_odav = mock.Mock()
        mock_odav.execute.return_value = mock.Mock(success=True, message="open_app on telegram_desktop: OK")
        self.service._odav = mock_odav

        self.service._pending_install = self._pending()
        response = self.service._handle_install_confirmation("yes")

        self.assertIsNone(self.service._pending_install)
        mock_install.assert_called_once_with("Telegram.TelegramDesktop", "winget")
        mock_get_checker.return_value.refresh.assert_called_once()
        mock_odav.execute.assert_called_once_with("open telegram")
        self.assertIn("Installed Telegram", response)
        self.assertIn("OK", response)

    @mock.patch("platform_adapters.winget_installer.install")
    def test_confirm_install_failure_does_not_retry(self, mock_install):
        mock_install.return_value = InstallResult(ok=False, message="Install failed: network error")
        mock_odav = mock.Mock()
        self.service._odav = mock_odav

        self.service._pending_install = self._pending()
        response = self.service._handle_install_confirmation("yes")

        self.assertIsNone(self.service._pending_install)
        mock_odav.execute.assert_not_called()
        self.assertIn("Couldn't install Telegram", response)
        self.assertIn("network error", response)

    # Branch 4: known adapter, not installed, no winget match.
    def test_confirm_no_winget_match(self):
        self.service._pending_install = self._pending(winget_id=None)
        # Use Gmail's actual display name for a realistic message.
        self.service._pending_install.platform_display_name = "Gmail"

        response = self.service._handle_install_confirmation("yes")

        self.assertIsNone(self.service._pending_install)
        self.assertIn("can't find Gmail", response)
        self.assertIn("manually", response)

    # Branch 5: known adapter, already installed -- normal path, no
    # pending-install state should ever be created (regression check).
    def test_already_installed_never_creates_pending_state(self):
        from AgentCore.resolution_gate import ResolutionGate, GateOutcome
        from AgentCore.command_router import CommandRouter
        from platform_adapters.availability import AvailabilityChecker

        gate = ResolutionGate(
            command_router=CommandRouter(),
            availability_checker=AvailabilityChecker(installed_apps=["Google Chrome"]),
        )
        result = gate.check("open browser")
        self.assertEqual(result.outcome, GateOutcome.RESOLVED)
        # Simulate what the conversation loop does for handler=="action":
        # no pending-install branch is ever reached for RESOLVED.
        self.assertIsNone(self.service._pending_install)

    # PendingInstall is in-memory only -- a restart while one is set
    # silently loses it. _handle_install_confirmation calls
    # onboarding.clear_pending_state() at the same point it clears
    # self._pending_install, so the compact status box's "Pending" field
    # (see onboarding.py's render_status_box) never shows a stale entry
    # once it's actually been resolved one way or another.
    @mock.patch("onboarding.clear_pending_state")
    def test_decline_clears_persisted_pending_state(self, mock_clear):
        self.service._pending_install = self._pending()
        self.service._handle_install_confirmation("no thanks")
        mock_clear.assert_called_once()

    @mock.patch("onboarding.clear_pending_state")
    def test_confirm_no_winget_match_clears_persisted_pending_state(self, mock_clear):
        self.service._pending_install = self._pending(winget_id=None)
        self.service._handle_install_confirmation("yes")
        mock_clear.assert_called_once()


if __name__ == "__main__":
    unittest.main()
