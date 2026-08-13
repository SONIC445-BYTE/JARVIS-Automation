"""
Security Broker approval-request pattern (§4.4c: "phone approves, desktop
acts"). Scaffold only: the shape of a request and the interface a real
Mobile Trust Companion would implement, no real phone, no real transport.

`SynchronousTestApprover` is a Track-A double for tests and for
exercising the T2 confirmation flow before a real companion app exists
-- it must never be selected by any code path outside tests.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ApprovalGate(Enum):
    """§4.4c's checkpoint-classification table, verbatim."""
    PASSWORD_FIELD = "password_field"
    OTP_RECEIVED = "otp_received"
    CAPTCHA = "captcha"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    DELETE_FILES = "delete_files"
    BANK_TRANSFER = "bank_transfer"
    ADMIN_PRIVILEGE = "admin_privilege"


@dataclass(frozen=True)
class ApprovalRequest:
    """
    `rendered_description` must describe the actual action, e.g. "JARVIS
    wants to send Rs.2,000 via UPI" -- never a summary of several actions
    collapsed into one ask. Matches trust_tier_clinical_writes.md's
    "rendered from the payload that will actually be sent" rule, applied
    here one tier down even though T2 doesn't require it as strictly.
    """
    gate: ApprovalGate
    rendered_description: str
    session_id: str


class ApprovalResponder(ABC):
    """
    What a real Mobile Trust Companion implements. No real implementation
    exists yet -- Stage 1c / its own phase, needs an actual paired device.
    """

    @abstractmethod
    def request_approval(self, request: ApprovalRequest) -> bool:
        """Returns True if approved. Must never raise to mean "denied" -- denial is a real False, not an exception a caller might mishandle as "unknown, proceed"."""


class SynchronousTestApprover(ApprovalResponder):
    """
    Track-A test double. Fixed pre-programmed answer, records every
    request it was asked to decide so tests can assert on what was
    actually rendered, not just the final boolean.
    """

    def __init__(self, decision: bool = True):
        self.decision = decision
        self.requests_seen: list[ApprovalRequest] = []

    def request_approval(self, request: ApprovalRequest) -> bool:
        self.requests_seen.append(request)
        return self.decision
