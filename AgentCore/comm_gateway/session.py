"""
Session -- the object the Communication Gateway hands to everything
downstream. "Session Manager must never know which channel a session
originated from" (§4.4c).

Enforced structurally, not by convention: Session has no channel field.
Not a hidden one, not a private one under a different name -- it is
absent from the class entirely, so there is no attribute a downstream
consumer could reach for even by accident. The channel identity lives
only inside gateway.py's own audit trail, which is a compliance record,
not something Session Manager code paths can query.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional

from AgentCore.comm_gateway.audit import emit_gateway_event
from AgentCore.comm_gateway.capability import CapabilitySet


@dataclass(frozen=True)
class Session:
    session_id: str
    principal: str  # the authenticated identifier, NOT the channel it arrived on
    capabilities: CapabilitySet
    created_at: float
    trust_expires_at: float

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.trust_expires_at

    @staticmethod
    def new(principal: str, capabilities: CapabilitySet, trust_expires_at: float) -> "Session":
        return Session(
            session_id=str(uuid.uuid4()),
            principal=principal,
            capabilities=capabilities,
            created_at=time.time(),
            trust_expires_at=trust_expires_at,
        )


class SessionManager:
    """
    Only ever sees Session objects. `register()` refuses to overwrite an
    existing session_id -- this is what makes "never renegotiated upward
    mid-session" a checked property rather than a promise: even if a
    caller computed a new, more permissive CapabilitySet and tried to
    attach it to an existing session_id, this refuses.
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def register(self, session: Session) -> None:
        if session.session_id in self._sessions:
            emit_gateway_event(
                event_type="renegotiation_refused",
                channel_kind="unknown",  # SessionManager never learns the channel either
                outcome_ok=False,
                detail={"session_id": session.session_id},
            )
            raise ValueError(
                f"session {session.session_id} already registered -- "
                f"a session's capabilities are fixed for its lifetime, "
                f"create a new session rather than replacing this one"
            )
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is None or session.is_expired():
            return None
        return session

    def revoke(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
