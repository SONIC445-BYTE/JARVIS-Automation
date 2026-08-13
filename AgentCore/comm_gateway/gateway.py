"""
CommunicationGateway -- orchestrates channel -> auth -> capability
negotiation -> Session. The single place channel identity and Session
identity meet; everything past `connect()`'s return value only sees the
Session.
"""
from __future__ import annotations

import time
from typing import Optional

from AgentCore.comm_gateway.audit import emit_gateway_event
from AgentCore.comm_gateway.auth import AuthenticationError, AuthHandshake
from AgentCore.comm_gateway.capability import CapabilityNegotiator, PG001Mode
from AgentCore.comm_gateway.channel import Channel
from AgentCore.comm_gateway.deployment_policy import DeploymentPolicy, load_deployment_policy
from AgentCore.comm_gateway.session import Session, SessionManager


class CommunicationGateway:
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        auth: Optional[AuthHandshake] = None,
        negotiator: Optional[CapabilityNegotiator] = None,
        policy: Optional[DeploymentPolicy] = None,
    ):
        self.session_manager = session_manager or SessionManager()
        self.auth = auth or AuthHandshake()
        self.negotiator = negotiator or CapabilityNegotiator()
        self.policy = policy or load_deployment_policy()

    def connect(
        self,
        channel: Channel,
        declared_mode: PG001Mode,
        second_factor: Optional[str] = None,
    ) -> Session:
        """
        Raises AuthenticationError on a failed handshake -- no Session is
        created or registered. `declared_mode` is required, not defaulted:
        Mode C's whole safety property is that the mode is DECLARED, not
        inferred, and defaulting it here would be inferring it by another
        name.
        """
        identity = channel.identify()

        if channel.requires_second_factor():
            trust = self.auth.authenticate(identity, second_factor)
            principal, expires_at = trust.principal, trust.expires_at
        else:
            principal, expires_at = identity.claimed_identifier, time.time() + self.auth.session_ttl_s

        capabilities = self.negotiator.negotiate(channel, declared_mode, self.policy)
        session = Session.new(principal=principal, capabilities=capabilities, trust_expires_at=expires_at)
        self.session_manager.register(session)

        emit_gateway_event(
            event_type="session_created",
            channel_kind=identity.channel_kind.value,
            outcome_ok=True,
            detail={
                "session_id": session.session_id,
                "mode": capabilities.mode.value,
                "max_tier": capabilities.max_tier.name,
            },
        )
        return session
