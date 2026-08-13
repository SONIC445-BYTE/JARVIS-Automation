"""
CommunicationGateway.connect() -- the real, unmocked flow:
channel.identify() -> auth (if required) -> capability negotiation ->
Session -> registered -> audited.

Mocks nothing on the audit side, matching D16's
TestAgainstTheRealAuditLog convention: runs the real AppendOnlyAuditLog
(redirected by conftest.py's autouse fixture) and reads back what
actually landed on disk. Argument assertions can't catch a record the
storage engine rejects or mangles.
"""
import unittest

from AgentCore.comm_gateway.audit import get_gateway_audit_log
from AgentCore.comm_gateway.auth import AuthenticationError, AuthHandshake, PairingStore
from AgentCore.comm_gateway.capability import PG001Mode, TrustTier
from AgentCore.comm_gateway.channel import DesktopChannel, SyntheticRemoteChannel
from AgentCore.comm_gateway.deployment_policy import DeploymentMode, DeploymentPolicy
from AgentCore.comm_gateway.gateway import CommunicationGateway


class TestDesktopConnectFlow(unittest.TestCase):
    def test_desktop_connects_with_no_second_factor_and_gets_a_real_session(self):
        gw = CommunicationGateway(policy=DeploymentPolicy())
        session = gw.connect(DesktopChannel(), declared_mode=PG001Mode.PERSONAL)
        self.assertIsNotNone(session)
        self.assertTrue(session.capabilities.permits(TrustTier.T2_CONSEQUENTIAL))
        self.assertIs(gw.session_manager.get(session.session_id), session)


class TestRemoteConnectFlow(unittest.TestCase):
    def setUp(self):
        self.store = PairingStore()
        self.store.register("physician-1", "654321")
        self.gw = CommunicationGateway(
            policy=DeploymentPolicy(mode=DeploymentMode.SECURE_REMOTE, remote_voice_enabled=True),
            auth=AuthHandshake(pairing_store=self.store),
        )

    def test_correct_second_factor_connects(self):
        channel = SyntheticRemoteChannel("physician-1")
        session = self.gw.connect(channel, declared_mode=PG001Mode.PERSONAL, second_factor="654321")
        self.assertEqual(session.principal, "physician-1")
        self.assertEqual(session.capabilities.max_tier, TrustTier.T1_DISCLOSING_READ)

    def test_missing_second_factor_raises_and_creates_no_session(self):
        channel = SyntheticRemoteChannel("physician-1")
        sessions_before = len(self.gw.session_manager._sessions)
        with self.assertRaises(AuthenticationError):
            self.gw.connect(channel, declared_mode=PG001Mode.PERSONAL, second_factor=None)
        self.assertEqual(len(self.gw.session_manager._sessions), sessions_before)


class TestRealAuditTrail(unittest.TestCase):
    """No mocking on the audit side -- reads the real log back from disk."""

    def test_a_successful_connect_writes_a_real_verifiable_audit_entry(self):
        gw = CommunicationGateway(policy=DeploymentPolicy())
        session = gw.connect(DesktopChannel(), declared_mode=PG001Mode.PROTECTED)

        log = get_gateway_audit_log()
        entries = log.get_entries(limit=10)
        created = [e for e in entries if e["event"] == "session_created"]
        self.assertTrue(created)
        self.assertEqual(created[-1]["detail"]["session_id"], session.session_id)
        self.assertEqual(created[-1]["detail"]["mode"], "B")
        self.assertTrue(log.verify_integrity())

    def test_the_session_id_in_the_audit_log_never_carries_channel_identity(self):
        """
        A different flavor of the opacity property: even the AUDIT
        record -- which is allowed to know the channel, unlike Session
        Manager -- must key on session_id, not leak the channel's
        claimed_identifier into a field a downstream reader might
        mistake for the authenticated principal.
        """
        gw = CommunicationGateway(policy=DeploymentPolicy())
        gw.connect(DesktopChannel(), declared_mode=PG001Mode.PERSONAL)
        entries = get_gateway_audit_log().get_entries(limit=10)
        created = [e for e in entries if e["event"] == "session_created"][-1]
        self.assertIn("session_id", created["detail"])
        self.assertNotIn("claimed_identifier", created["detail"])


if __name__ == "__main__":
    unittest.main()
