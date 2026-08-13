"""
Capability Negotiation (§4.4c PG-001 + the v3.9 trust-tier resolution,
`docs/trust_tier_clinical_writes.md`).

"When a session connects, it receives an explicit capability set... the
tier is a property of the action; the capability set is a property of
the session; only one is negotiable. Capability Negotiation supplies
(max tier, available confirmation modalities) at connect, fixed for the
session's lifetime and never re-negotiated upward mid-session."

This module computes that pair. Enforcing "never upward mid-session" is
this module's job at computation time (it is a pure function of policy +
channel + declared mode, called once); enforcing that nothing can swap
in a different result for an existing session afterward is
session.SessionManager's job -- see its `register()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet

from AgentCore.comm_gateway.channel import Channel, ChannelKind
from AgentCore.comm_gateway.deployment_policy import DeploymentPolicy


class PG001Mode(Enum):
    """PG-001's three deployment modes. Session-declared at connect, never inferred -- same principle Mode C's own gate uses for clinical/non-clinical."""
    PERSONAL = "A"
    PROTECTED = "B"
    STRICT_CLINICAL = "C"


class TrustTier(Enum):
    """docs/trust_tier_clinical_writes.md's four tiers, by irreversibility and liability."""
    T0_LOCAL = 0
    T1_DISCLOSING_READ = 1
    T2_CONSEQUENTIAL = 2
    T3_CLINICAL_WRITE = 3


#: Channels the DESIGN intends to eventually carry T3 (docs/
#: trust_tier_clinical_writes.md names desk-side voice with a
#: distinguishing spoken token AND the Security Broker's companion
#: device as the two valid confirmation channels -- desktop is not
#: excluded by design). Empty here regardless, because this phase does
#: not build the four-invariant-property confirmation mechanism itself
#: (payload-rendered presentation, distinguishing-token consent, bounded
#: validity, silence-is-refusal) for ANY channel -- see approval.py. A
#: channel cannot be marked T3-capable before the thing that would make
#: it honest exists. Fact about what is built in this phase, not a
#: permanent statement that desktop can never reach T3.
_T3_CAPABLE_CHANNELS: FrozenSet[ChannelKind] = frozenset()


@dataclass(frozen=True)
class CapabilitySet:
    """
    The negotiated result. Frozen -- there is no setter, by construction,
    for "renegotiate upward." A new CapabilitySet can always be computed;
    what matters is that SessionManager refuses to attach one to an
    existing session (see session.py).
    """
    mode: PG001Mode
    remote_voice: bool
    patient_discussion: bool
    rhinal_writes: bool
    email_requires_confirmation: bool
    max_tier: TrustTier
    confirmation_modalities: FrozenSet[str]

    def permits(self, tier: TrustTier) -> bool:
        return tier.value <= self.max_tier.value


class CapabilityNegotiator:
    """
    One entry point: negotiate(). No incremental "add a capability"
    method exists on this class or on CapabilitySet -- that absence is
    deliberate, not an oversight.
    """

    def negotiate(self, channel: Channel, declared_mode: PG001Mode, policy: DeploymentPolicy) -> CapabilitySet:
        is_remote = channel.kind is not ChannelKind.DESKTOP

        if is_remote and not policy.allows_remote_channels():
            # STRICT_LOCAL: a remote channel gets a capability set, but an
            # empty one -- T0 only, nothing enabled. Refusing to even
            # negotiate would leak "a remote channel tried to connect" as
            # a distinguishable error from "a remote channel connected but
            # got nothing"; both should look the same from outside.
            return CapabilitySet(
                mode=declared_mode,
                remote_voice=False,
                patient_discussion=False,
                rhinal_writes=False,
                email_requires_confirmation=True,
                max_tier=TrustTier.T0_LOCAL,
                confirmation_modalities=frozenset(),
            )

        remote_voice = (not is_remote) or policy.remote_voice_enabled
        # Mode C blocks REMOTE clinical discussion by declared intent,
        # matching AgentCore/privacy_gateway's gate exactly -- the
        # declaration is the primary control here too, not an inference.
        # Local/desktop clinical discussion is ordinary work and is never
        # blocked by this, regardless of declared mode.
        patient_discussion = (not is_remote) or (declared_mode is not PG001Mode.STRICT_CLINICAL)

        if channel.kind in _T3_CAPABLE_CHANNELS:
            max_tier = TrustTier.T3_CLINICAL_WRITE  # unreachable today; _T3_CAPABLE_CHANNELS is empty
        elif is_remote:
            # Remote channels cap at T1, not T2: nothing built in this
            # phase provides an honest Security-Broker-style approval
            # flow over a remote transport, so no remote action can
            # honestly clear even the consequential tier yet.
            max_tier = TrustTier.T1_DISCLOSING_READ
        else:
            max_tier = TrustTier.T2_CONSEQUENTIAL

        modalities = {"keyboard", "spoken_token"} if not is_remote else set()

        return CapabilitySet(
            mode=declared_mode,
            remote_voice=remote_voice,
            patient_discussion=patient_discussion,
            rhinal_writes=not is_remote,
            email_requires_confirmation=True,
            max_tier=max_tier,
            confirmation_modalities=frozenset(modalities),
        )
