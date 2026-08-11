"""
Learning Audit Log — Immutable append-only log with HMAC signatures
=====================================================================
Records all proposed/approved/auto actions with tamper evidence.

DEC-002 (2026-07-31): now a thin wrapper over
AgentCore.audit_trail.AppendOnlyAuditLog, the shared engine also used
by the clinical action audit trail, rather than a second, separately-
maintained implementation of the same append-only + HMAC-chain logic.
Reused because the chaining design here was already solid; what
genuinely needed rework (confirmed by reading this file, not assumed):
the key used to be computed once at *module import time*
(`_HMAC_KEY = os.environ.get('JARVIS_HMAC_KEY', 'jarvis-learning-audit-
default-key').encode()`) -- the identical D2/D14 hardcoded-default-key
weakness, plus it ran before any fail-closed check could even happen.
And log_event()'s actual file write had no try/except at all, so a
transient write failure (disk full, permission error) would propagate
uncaught to whatever called it -- no distinction from a configuration
failure, and no recovery path. Both fixed via the shared engine: key
resolution is fail-closed at construction (secure_key.resolve_key(),
same as memory_store.py/mode_manager/audit.py), and transient write
failures are queued to a fallback file and reconciled automatically
rather than crashing the caller.

Public API (log_event/verify_log_integrity/get_entries/get_stats)
unchanged -- nothing that already imports LearningAuditLog needed to
change.
"""

from pathlib import Path
from typing import Dict, List, Optional

from AgentCore.audit_trail import AppendOnlyAuditLog


class LearningAuditLog:
    """Append-only HMAC-signed audit log for the learning system."""

    def __init__(self, log_path: Optional[str] = None):
        if log_path is None:
            root = Path(__file__).resolve().parents[2]
            log_path = root / 'data' / 'audit' / 'learning_audit.log'
        self._log = AppendOnlyAuditLog(
            log_path=Path(log_path),
            key_purpose="learning_audit",
            key_env_var="JARVIS_HMAC_KEY",
        )

    def log_event(self, event_type: str, payload: dict) -> dict:
        """
        Append an event to the audit log.

        Args:
            event_type: e.g. 'action_proposed', 'action_approved',
                        'auto_executed', 'adapter_generated', etc.
            payload: Arbitrary JSON-serialisable data.

        Returns:
            The written entry dict. Note: a transient write failure no
            longer raises -- it's queued to a fallback file and
            reconciled automatically. Callers that need to know whether
            the write itself succeeded should call the shared engine's
            append() directly via self._log for the full
            AuditWriteResult; this method preserves the original
            "returns the entry dict" contract for existing callers.
        """
        result = self._log.append({'type': event_type, 'payload': payload})
        return result.entry

    def verify_log_integrity(self) -> bool:
        """Verify the entire log: check HMAC chain and individual signatures."""
        return self._log.verify_integrity()

    def get_entries(self, limit: int = 100) -> List[dict]:
        """Return the last *limit* entries."""
        return self._log.get_entries(limit)

    def get_stats(self) -> dict:
        entries = self.get_entries(limit=999_999)
        from collections import Counter
        types = Counter(e.get('type') for e in entries)
        return {
            'total_entries': len(entries),
            'by_type': dict(types),
            'integrity_ok': self.verify_log_integrity(),
        }
