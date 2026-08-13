"""
Audit coverage for the Communication Gateway, reusing DEC-002's engine.

Same pattern as AgentCore/mcp_audit.py and AgentCore/privacy_gateway's
Mode C gate: import AgentCore.audit_trail.AppendOnlyAuditLog and its
two-tier failure model, never modify it. A new module because this is
call-site policy (what a gateway event looks like, when it fires) for
one class of caller, not storage or record shape.

What gets logged here: session creation, authentication failure,
capability negotiation outcome. NOT the DEC-002 clinical-action shape
(who/what/when/why/source/consent) -- an auth event isn't a clinical
action, and reusing that record shape for it would blur the two in any
export or review. Own record shape, same engine, same file-per-caller
discipline `docs/trust_tier_clinical_writes.md` §6 already establishes
for the confirmation-request pattern.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Any, Dict, Optional

from AgentCore.audit_trail import AppendOnlyAuditLog, AuditWriteResult

LOG_DIR_ENV_VAR = "JARVIS_COMM_GATEWAY_LOG_DIR"
DEFAULT_LOG_DIR = "data/comm_gateway"
KEY_ENV_VAR = "JARVIS_COMM_GATEWAY_AUDIT_KEY"
KEY_PURPOSE = "comm_gateway"

_log: Optional[AppendOnlyAuditLog] = None


def get_gateway_audit_log() -> AppendOnlyAuditLog:
    """
    Lazy singleton, same discipline as audit_trail.get_clinical_audit_log():
    constructed on first real use so importing this module never triggers
    key resolution. Configuration failure (no key resolvable) propagates
    uncaught -- a hard stop, not something this module papers over.
    """
    global _log
    if _log is None:
        log_dir = Path(os.environ.get(LOG_DIR_ENV_VAR, DEFAULT_LOG_DIR))
        _log = AppendOnlyAuditLog(
            log_path=log_dir / "gateway_events.log",
            key_purpose=KEY_PURPOSE,
            key_env_var=KEY_ENV_VAR,
        )
    return _log


def reset_gateway_audit_log_singleton_for_tests() -> None:
    global _log
    _log = None


def emit_gateway_event(
    *,
    event_type: str,
    channel_kind: str,
    outcome_ok: bool,
    detail: Optional[Dict[str, Any]] = None,
    log: Optional[AppendOnlyAuditLog] = None,
) -> AuditWriteResult:
    """
    session_created | auth_failed | renegotiation_refused.

    `who` is getpass.getuser() -- same honest limit DEC-002 already states:
    the OS account running JARVIS, not a verified remote identity. For a
    remote channel that is exactly the point being audited: the gateway
    does not yet know who is really on the other end, only that a second
    factor was presented and checked.
    """
    log = log or get_gateway_audit_log()
    entry_fields = {
        "who": getpass.getuser(),
        "event": event_type,
        "channel_kind": channel_kind,
        "ok": outcome_ok,
        "detail": detail or {},
    }
    return log.append(entry_fields)
