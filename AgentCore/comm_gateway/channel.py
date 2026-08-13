"""
Channel abstraction -- §4.4c's "all channels terminate here" layer.

`ChannelKind.DESKTOP` is the only channel that is real, in the sense of
touching the actual running system: it is the machine JARVIS already
runs voice on. Real remote channels (phone/WhatsApp/Telegram/WebRTC) are
Stage 1c work -- they need actual telephony/messaging integration this
phase does not build. `ChannelKind.SYNTHETIC_TEST` exists only so the
gateway's remote-channel code paths (second-factor auth, capability
negotiation for a non-local channel) are exercisable and tested before
any real remote channel exists, per the Track A/Track B split: this is
the Track A double, never a stand-in for "channel testing was skipped."
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChannelKind(Enum):
    DESKTOP = "desktop"
    SYNTHETIC_TEST = "synthetic_test"
    # Stage 1c, not implemented: PHONE, WHATSAPP, TELEGRAM, WEBRTC.


@dataclass(frozen=True)
class ChannelIdentity:
    """
    What a channel claims about who is connecting, BEFORE authentication.

    Deliberately weak on its own -- "phone-number identity alone is
    insufficient" (§Stage 1c) applies to every remote channel, not just
    phones. This is the pre-auth claim the handshake in auth.py must not
    trust by itself.
    """
    channel_kind: ChannelKind
    claimed_identifier: str  # e.g. a phone number, or "local" for desktop
    connection_id: str


class Channel:
    """
    Base for anything that can produce a ChannelIdentity. A real channel
    implementation (Stage 1c) would also carry the actual transport --
    the socket, the WhatsApp webhook payload, the SIM registration. This
    scaffold only needs identify(); the transport is out of scope here.
    """

    kind: ChannelKind

    def identify(self) -> ChannelIdentity:
        raise NotImplementedError

    def requires_second_factor(self) -> bool:
        """
        Whether this channel needs auth.AuthHandshake before a Session can
        be created. Overridden per channel, not inferred from the kind at
        call sites -- inferring behaviour from an enum value elsewhere is
        exactly the "read the source, never the name" failure this
        project has already been burned by twice (GeneratorHelper/
        LLMAdapter, vaultWorthy).
        """
        raise NotImplementedError


class DesktopChannel(Channel):
    """
    The local machine. Explicitly exempted from the second-factor
    handshake, and the reason is stated rather than left implicit: there
    is no remote party to authenticate. The OS session boundary IS the
    auth boundary here, the same honest limit DEC-002's audit trail
    already states for `who` (the OS account, not a verified physician
    identity) -- this does not strengthen that limit or weaken it, it is
    the same fact restated at the channel layer.
    """

    kind = ChannelKind.DESKTOP

    def identify(self) -> ChannelIdentity:
        import getpass
        return ChannelIdentity(
            channel_kind=self.kind,
            claimed_identifier=getpass.getuser(),
            connection_id=str(uuid.uuid4()),
        )

    def requires_second_factor(self) -> bool:
        return False


class SyntheticRemoteChannel(Channel):
    """
    Track A test double for a remote channel. Behaves like a real remote
    channel would for everything the gateway can actually test today:
    requires a second factor, carries a claimed (unverified) identifier.
    Never wired to a real transport -- there is nothing to send or
    receive, `identify()` returns a value the caller supplies.
    """

    kind = ChannelKind.SYNTHETIC_TEST

    def __init__(self, claimed_identifier: str = "synthetic-test-principal"):
        self._claimed_identifier = claimed_identifier

    def identify(self) -> ChannelIdentity:
        return ChannelIdentity(
            channel_kind=self.kind,
            claimed_identifier=self._claimed_identifier,
            connection_id=str(uuid.uuid4()),
        )

    def requires_second_factor(self) -> bool:
        return True
