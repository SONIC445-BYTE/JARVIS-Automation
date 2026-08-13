"""
"Authentication is a hard prerequisite: second factor (PIN/pairing),
session-based trust with timeout... Phone-number identity alone is
insufficient." (§Stage 1c)
"""
import time
import unittest

from AgentCore.comm_gateway.audit import get_gateway_audit_log
from AgentCore.comm_gateway.auth import AuthenticationError, AuthHandshake, PairingStore
from AgentCore.comm_gateway.channel import ChannelIdentity, ChannelKind, DesktopChannel, SyntheticRemoteChannel


class TestDesktopExemptFromSecondFactor(unittest.TestCase):
    def test_desktop_channel_requires_no_second_factor(self):
        self.assertFalse(DesktopChannel().requires_second_factor())


class TestRemoteChannelFailsClosed(unittest.TestCase):
    def setUp(self):
        self.store = PairingStore()
        self.handshake = AuthHandshake(pairing_store=self.store)
        self.identity = ChannelIdentity(
            channel_kind=ChannelKind.SYNTHETIC_TEST,
            claimed_identifier="physician-1",
            connection_id="conn-1",
        )

    def test_no_second_factor_presented_raises_and_no_session_data_returned(self):
        with self.assertRaises(AuthenticationError):
            self.handshake.authenticate(self.identity, None)

    def test_wrong_pin_raises(self):
        self.store.register("physician-1", "123456")
        with self.assertRaises(AuthenticationError):
            self.handshake.authenticate(self.identity, "000000")

    def test_pin_for_a_different_principal_does_not_authenticate_this_one(self):
        """Phone-number-identity-alone-is-insufficient's sharpest case: claiming to be
        someone whose PIN you don't have must fail even if SOME valid PIN exists in the store."""
        self.store.register("someone-else", "999999")
        with self.assertRaises(AuthenticationError):
            self.handshake.authenticate(self.identity, "999999")

    def test_correct_pin_authenticates_and_issues_a_bounded_trust_record(self):
        self.store.register("physician-1", "123456")
        before = time.time()
        trust = self.handshake.authenticate(self.identity, "123456")
        self.assertEqual(trust.principal, "physician-1")
        self.assertGreater(trust.expires_at, before)
        self.assertFalse(trust.is_expired(now=before))
        self.assertTrue(trust.is_expired(now=trust.expires_at + 1))

    def test_failed_attempt_is_audited(self):
        with self.assertRaises(AuthenticationError):
            self.handshake.authenticate(self.identity, "wrong")
        entries = get_gateway_audit_log().get_entries(limit=10)
        self.assertTrue(any(e["event"] == "auth_failed" and e["ok"] is False for e in entries))


if __name__ == "__main__":
    unittest.main()
