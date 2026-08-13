"""
Capability Negotiation -- "fixed for the session's lifetime and never
re-negotiated upward mid-session" (§4.4c / docs/trust_tier_clinical_writes.md).
"""
import unittest

from AgentCore.comm_gateway.audit import get_gateway_audit_log
from AgentCore.comm_gateway.capability import CapabilityNegotiator, PG001Mode, TrustTier
from AgentCore.comm_gateway.channel import DesktopChannel, SyntheticRemoteChannel
from AgentCore.comm_gateway.deployment_policy import DeploymentMode, DeploymentPolicy
from AgentCore.comm_gateway.session import Session, SessionManager


class TestNegotiationComputation(unittest.TestCase):
    def setUp(self):
        self.negotiator = CapabilityNegotiator()

    def test_strict_local_gives_a_remote_channel_nothing(self):
        policy = DeploymentPolicy(mode=DeploymentMode.STRICT_LOCAL)
        caps = self.negotiator.negotiate(SyntheticRemoteChannel(), PG001Mode.PERSONAL, policy)
        self.assertEqual(caps.max_tier, TrustTier.T0_LOCAL)
        self.assertFalse(caps.remote_voice)
        self.assertFalse(caps.patient_discussion)
        self.assertFalse(caps.rhinal_writes)
        self.assertEqual(caps.confirmation_modalities, frozenset())

    def test_strict_local_still_gives_desktop_full_local_capability(self):
        """STRICT_LOCAL restricts REMOTE channels; it must not accidentally cripple the local desktop channel too."""
        policy = DeploymentPolicy(mode=DeploymentMode.STRICT_LOCAL)
        caps = self.negotiator.negotiate(DesktopChannel(), PG001Mode.PERSONAL, policy)
        self.assertEqual(caps.max_tier, TrustTier.T2_CONSEQUENTIAL)
        self.assertTrue(caps.remote_voice)
        self.assertTrue(caps.rhinal_writes)

    def test_secure_remote_still_caps_remote_below_t2(self):
        """No channel built in this phase can honestly clear T2 over a remote transport -- see capability.py's comment on why."""
        policy = DeploymentPolicy(mode=DeploymentMode.SECURE_REMOTE, remote_voice_enabled=True)
        caps = self.negotiator.negotiate(SyntheticRemoteChannel(), PG001Mode.PERSONAL, policy)
        self.assertEqual(caps.max_tier, TrustTier.T1_DISCLOSING_READ)
        self.assertFalse(caps.permits(TrustTier.T2_CONSEQUENTIAL))

    def test_no_channel_built_in_this_phase_reaches_t3(self):
        for channel in (DesktopChannel(), SyntheticRemoteChannel()):
            for mode in DeploymentMode:
                policy = DeploymentPolicy(mode=mode, remote_voice_enabled=True)
                caps = self.negotiator.negotiate(channel, PG001Mode.PERSONAL, policy)
                self.assertFalse(
                    caps.permits(TrustTier.T3_CLINICAL_WRITE),
                    f"{channel.kind} under {mode} must not reach T3 -- "
                    f"the confirmation mechanism for it isn't built yet",
                )

    def test_strict_clinical_mode_blocks_remote_patient_discussion(self):
        policy = DeploymentPolicy(mode=DeploymentMode.SECURE_REMOTE, remote_voice_enabled=True)
        caps = self.negotiator.negotiate(SyntheticRemoteChannel(), PG001Mode.STRICT_CLINICAL, policy)
        self.assertFalse(caps.patient_discussion)

    def test_strict_clinical_mode_does_not_block_local_patient_discussion(self):
        """Mode C blocks REMOTE clinical discussion by declared intent, not local -- in-person work is unaffected by declaring Strict Clinical for a session."""
        policy = DeploymentPolicy(mode=DeploymentMode.STRICT_LOCAL)
        caps = self.negotiator.negotiate(DesktopChannel(), PG001Mode.STRICT_CLINICAL, policy)
        self.assertTrue(caps.patient_discussion)


class TestNeverRenegotiatedUpward(unittest.TestCase):
    """
    Not just "CapabilitySet is a frozen dataclass" (true, but only proves
    a single instance can't be mutated) -- proves SessionManager refuses
    to let a session_id be re-registered with a different, more
    permissive result at all.
    """

    def test_registering_the_same_session_id_twice_is_refused(self):
        negotiator = CapabilityNegotiator()
        weak_caps = negotiator.negotiate(
            SyntheticRemoteChannel(), PG001Mode.PERSONAL, DeploymentPolicy(mode=DeploymentMode.STRICT_LOCAL)
        )
        strong_caps = negotiator.negotiate(
            DesktopChannel(), PG001Mode.PERSONAL, DeploymentPolicy(mode=DeploymentMode.STRICT_LOCAL)
        )

        manager = SessionManager()
        session = Session.new(principal="p", capabilities=weak_caps, trust_expires_at=9e12)
        manager.register(session)

        # Attempt to "upgrade" the same session_id to a stronger capability set.
        upgraded = Session(
            session_id=session.session_id,
            principal=session.principal,
            capabilities=strong_caps,
            created_at=session.created_at,
            trust_expires_at=session.trust_expires_at,
        )
        with self.assertRaises(ValueError):
            manager.register(upgraded)

        # The originally registered (weaker) session is still what's on file.
        self.assertEqual(manager.get(session.session_id).capabilities, weak_caps)

        # The refusal itself is a real audited event, not only a raised
        # exception a caller could catch and quietly retry past.
        entries = get_gateway_audit_log().get_entries(limit=10)
        refused = [e for e in entries if e["event"] == "renegotiation_refused"]
        self.assertTrue(refused, "the refused re-registration must be audited")
        self.assertEqual(refused[-1]["detail"]["session_id"], session.session_id)
        self.assertFalse(refused[-1]["ok"])

    def test_expired_sessions_are_not_returned(self):
        negotiator = CapabilityNegotiator()
        caps = negotiator.negotiate(DesktopChannel(), PG001Mode.PERSONAL, DeploymentPolicy())
        manager = SessionManager()
        session = Session.new(principal="p", capabilities=caps, trust_expires_at=0.0)  # already expired
        manager.register(session)
        self.assertIsNone(manager.get(session.session_id))


if __name__ == "__main__":
    unittest.main()
