"""
"Session Manager must never know which channel a session originated
from" (§4.4c) -- tested as a structural property of Session, not asserted
in prose.
"""
import dataclasses
import unittest

from AgentCore.comm_gateway.capability import CapabilityNegotiator, PG001Mode
from AgentCore.comm_gateway.channel import DesktopChannel, SyntheticRemoteChannel
from AgentCore.comm_gateway.deployment_policy import DeploymentMode, DeploymentPolicy
from AgentCore.comm_gateway.session import Session


class TestSessionHasNoChannelField(unittest.TestCase):
    def test_session_dataclass_fields_never_include_channel(self):
        field_names = {f.name for f in dataclasses.fields(Session)}
        for suspicious in ("channel", "channel_kind", "transport", "connection_id"):
            self.assertNotIn(
                suspicious, field_names,
                f"Session must not carry {suspicious!r} -- that is exactly "
                f"the channel-identifying information downstream code must not see",
            )

    def test_capability_set_also_carries_no_channel_identifying_field(self):
        """
        The opacity property would be trivially defeated if Session
        itself had no channel field but CapabilitySet (which Session
        embeds) did. Checked one level down too.
        """
        from AgentCore.comm_gateway.capability import CapabilitySet
        field_names = {f.name for f in dataclasses.fields(CapabilitySet)}
        for suspicious in ("channel", "channel_kind", "transport"):
            self.assertNotIn(suspicious, field_names)

    def test_desktop_and_remote_sessions_are_the_same_shape(self):
        """
        Not "equal" (session_id/created_at/principal differ by
        construction) but the same set of fields with the same types --
        nothing about the Session class itself branches on which channel
        produced the CapabilitySet it was built from.
        """
        policy = DeploymentPolicy(mode=DeploymentMode.SECURE_REMOTE, remote_voice_enabled=True)
        negotiator = CapabilityNegotiator()

        caps_desktop = negotiator.negotiate(DesktopChannel(), PG001Mode.PERSONAL, policy)
        caps_remote = negotiator.negotiate(SyntheticRemoteChannel("remote-principal"), PG001Mode.PERSONAL, policy)

        s1 = Session.new(principal="desktop-principal", capabilities=caps_desktop, trust_expires_at=999999999.0)
        s2 = Session.new(principal="remote-principal", capabilities=caps_remote, trust_expires_at=999999999.0)

        self.assertEqual(
            {f.name for f in dataclasses.fields(s1)},
            {f.name for f in dataclasses.fields(s2)},
        )
        self.assertEqual(type(s1.capabilities), type(s2.capabilities))


if __name__ == "__main__":
    unittest.main()
