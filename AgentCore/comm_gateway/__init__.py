"""
Communication Gateway -- companion-app scaffolding (§4.4c).

Project structure, the auth handshake, and the Session-creation flow.
Not feature-complete: no real telephony/WhatsApp/Telegram/WebRTC channel
implementations, no real Mobile Trust Companion, no T3 action execution.
Those are separate, larger phases with their own real-world dependencies
(a live channel to integrate against, a physician to validate with).

Track A only. Nothing here can reach a real hospital system, real
patient data, or a live financial/record-modification action -- the
channels implemented are `DesktopChannel` (the machine JARVIS already
runs on) and a synthetic test double. Real remote channels (Stage 1c)
and T3 write execution (Stage 1a) stay gated on Stage 0.5, which is
independently blocked.
"""
from .approval import ApprovalGate, ApprovalRequest, ApprovalResponder, SynchronousTestApprover
from .auth import AuthenticationError, AuthHandshake, PairingStore
from .capability import CapabilitySet, CapabilityNegotiator, PG001Mode, TrustTier
from .channel import Channel, ChannelIdentity, ChannelKind, DesktopChannel, SyntheticRemoteChannel
from .deployment_policy import DeploymentMode, DeploymentPolicy, load_deployment_policy
from .gateway import CommunicationGateway
from .session import Session, SessionManager

__all__ = [
    "ApprovalGate", "ApprovalRequest", "ApprovalResponder", "SynchronousTestApprover",
    "AuthenticationError", "AuthHandshake", "PairingStore",
    "CapabilitySet", "CapabilityNegotiator", "PG001Mode", "TrustTier",
    "Channel", "ChannelIdentity", "ChannelKind", "DesktopChannel", "SyntheticRemoteChannel",
    "DeploymentMode", "DeploymentPolicy", "load_deployment_policy",
    "CommunicationGateway",
    "Session", "SessionManager",
]
