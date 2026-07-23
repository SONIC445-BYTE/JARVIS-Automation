"""
Phase 2c: ResolutionGate tests.

Covers the two-question gate's distinct outcomes using an injected fake
AvailabilityChecker so results are deterministic regardless of what's
actually installed on the machine running the tests.
"""
import unittest
from AgentCore.resolution_gate import ResolutionGate, GateOutcome
from AgentCore.command_router import CommandRouter
from platform_adapters.availability import AvailabilityChecker


class TestResolutionGate(unittest.TestCase):
    def _gate(self, installed_apps):
        checker = AvailabilityChecker(installed_apps=installed_apps)
        return ResolutionGate(command_router=CommandRouter(), availability_checker=checker)

    def test_platform_unknown_falls_through(self):
        gate = self._gate(installed_apps=[])
        result = gate.check("what is the capital of France?")
        self.assertEqual(result.outcome, GateOutcome.PLATFORM_UNKNOWN)

    def test_no_adapter_for_recognized_but_unwired_platform(self):
        # Netflix is a recognized platform name (audit-catalogued) but has
        # no working daemon adapter -- Q1 = no. Installed status doesn't
        # matter here; a fabricated adapter means installing wouldn't help.
        gate = self._gate(installed_apps=["Netflix"])
        result = gate.check("open netflix")
        self.assertEqual(result.outcome, GateOutcome.NO_ADAPTER)
        self.assertEqual(result.platform_display_name, "Netflix")
        self.assertIn("don't know how to control Netflix", result.message)

    def test_resolved_when_adapter_exists_and_installed(self):
        gate = self._gate(installed_apps=["Google Chrome"])
        result = gate.check("open browser")
        self.assertEqual(result.outcome, GateOutcome.RESOLVED)
        self.assertIsNotNone(result.intent)
        self.assertEqual(result.intent.adapter, "browser")

    def test_not_installed_when_adapter_exists_but_not_installed(self):
        gate = self._gate(installed_apps=[])
        result = gate.check("open telegram")
        self.assertEqual(result.outcome, GateOutcome.NOT_INSTALLED)
        self.assertEqual(result.adapter_key, "telegram_desktop")
        self.assertIn("isn't installed", result.message)
        self.assertIn("open_app", result.real_actions)
        self.assertIn("send_message", result.real_actions)
        self.assertEqual(result.winget_id, ("Telegram.TelegramDesktop", "winget"))

    def test_wired_platform_with_unmatched_verb_does_not_claim_no_adapter(self):
        # "whatsapp" IS wired (a real adapter exists), but no declared
        # verb matches this phrasing -- must fall through, not falsely
        # claim "I don't know how to control WhatsApp".
        gate = self._gate(installed_apps=[])
        result = gate.check("whatsapp is a messaging app")
        self.assertEqual(result.outcome, GateOutcome.PLATFORM_UNKNOWN)

    def test_gmail_has_no_winget_match(self):
        # Gmail is browser-based, not a separately installable desktop
        # app -- winget_id is correctly None, not a guessed/wrong id.
        gate = self._gate(installed_apps=[])
        result = gate.check("open gmail")
        self.assertEqual(result.outcome, GateOutcome.NOT_INSTALLED)
        self.assertIsNone(result.winget_id)


if __name__ == "__main__":
    unittest.main()
