"""
Auth handshake -- §Stage 1c: "Authentication is a hard prerequisite:
second factor (PIN/pairing), session-based trust with timeout, full
audit trail. Phone-number identity alone is insufficient."

`PairingStore` here is an in-memory, Track-A-only store. There is no
real secret distribution mechanism (no SMS/app pairing flow) -- that is
Stage 1c integration work against a real channel, not scaffolding. What
IS real: the fail-closed contract (no second factor presented or it does
not match -> AuthenticationError, no session, every attempt audited),
which is the part later real pairing mechanisms plug into without
changing.
"""
from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional

from AgentCore.comm_gateway.audit import emit_gateway_event
from AgentCore.comm_gateway.channel import ChannelIdentity
from AgentCore.secure_key import resolve_key


class AuthenticationError(Exception):
    """Second factor missing or wrong. No session is created when this is raised."""


@dataclass(frozen=True)
class SessionTrustRecord:
    principal: str          # the claimed_identifier that presented a valid second factor
    issued_at: float
    expires_at: float

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


class PairingStore:
    """
    Track-A in-memory pairing-code registry: `principal -> PIN`. A real
    deployment would replace this with a real pairing flow (QR code +
    device-bound token, most likely) without changing AuthHandshake's
    contract -- this class is the seam.
    """

    def __init__(self):
        self._codes: Dict[str, str] = {}

    def register(self, principal: str, pin: str) -> None:
        self._codes[principal] = pin

    def verify(self, principal: str, presented: str) -> bool:
        expected = self._codes.get(principal)
        if expected is None:
            return False
        # Constant-time compare -- a second-factor check is exactly the
        # kind of comparison a timing side-channel is worth denying for
        # free, even in a Track-A scaffold nothing real depends on yet.
        return hmac.compare_digest(expected, presented)


class AuthHandshake:
    """
    DesktopChannel skips this entirely (Channel.requires_second_factor()
    is False) -- the gateway checks that flag before ever calling here.
    Every other channel must present a second factor that verifies
    against the PairingStore, or authentication fails closed.
    """

    def __init__(self, pairing_store: Optional[PairingStore] = None, session_ttl_s: float = 3600.0):
        self.pairing_store = pairing_store or PairingStore()
        self.session_ttl_s = session_ttl_s
        # Resolved once, fail-closed at construction if unresolvable --
        # same discipline as every other audit-adjacent key in this
        # project. Currently unused for signing (nothing here is
        # persisted across process restarts yet), reserved for when
        # SessionTrustRecord needs to be handed back to a channel as a
        # verifiable token rather than held only in this process's memory.
        self._key = resolve_key("comm_gateway_pairing", "JARVIS_COMM_GATEWAY_PAIRING_KEY")

    def authenticate(self, identity: ChannelIdentity, second_factor: Optional[str]) -> SessionTrustRecord:
        if second_factor is None or not self.pairing_store.verify(identity.claimed_identifier, second_factor):
            emit_gateway_event(
                event_type="auth_failed",
                channel_kind=identity.channel_kind.value,
                outcome_ok=False,
                detail={"claimed_identifier": identity.claimed_identifier},
            )
            raise AuthenticationError(
                f"second factor rejected for {identity.claimed_identifier!r} "
                f"on channel {identity.channel_kind.value}"
            )
        now = time.time()
        return SessionTrustRecord(
            principal=identity.claimed_identifier,
            issued_at=now,
            expires_at=now + self.session_ttl_s,
        )

    def token_for_new_pairing(self) -> str:
        """A random PIN a real out-of-band channel (SMS, app screen) would deliver. Not cryptographically bound to anything yet -- see the constructor comment."""
        return f"{secrets.randbelow(1_000_000):06d}"
