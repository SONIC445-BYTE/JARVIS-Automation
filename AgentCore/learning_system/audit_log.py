"""
Learning Audit Log — Immutable append-only log with HMAC signatures
=====================================================================
Records all proposed/approved/auto actions with tamper evidence.
"""

import os
import json
import time
import hmac
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock


# HMAC key — in production, load from env or secure vault
_HMAC_KEY = os.environ.get('JARVIS_HMAC_KEY', 'jarvis-learning-audit-default-key').encode()


class LearningAuditLog:
    """
    Append-only HMAC-signed audit log for the learning system.

    Each line is a JSON object with an 'hmac' field computed over
    the rest of the payload + the previous line's HMAC (chaining).
    """

    GENESIS_HMAC = '0' * 64

    def __init__(self, log_path: Optional[str] = None):
        if log_path is None:
            root = Path(__file__).resolve().parents[2]
            log_path = root / 'data' / 'audit' / 'learning_audit.log'
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._seq = 0
        self._prev_hmac = self.GENESIS_HMAC
        self._load_state()

    # ------------------------------------------------------------------
    def _load_state(self):
        """Resume sequence counter and HMAC chain from existing log."""
        if not self._path.exists():
            return
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    self._seq = entry.get('seq', self._seq) + 1
                    self._prev_hmac = entry.get('hmac', self._prev_hmac)
        except Exception as e:
            print(f"[LearningAudit] Error loading state: {e}")

    # ------------------------------------------------------------------
    def log_event(self, event_type: str, payload: dict) -> dict:
        """
        Append an event to the audit log.

        Args:
            event_type: e.g. 'action_proposed', 'action_approved',
                        'auto_executed', 'adapter_generated', etc.
            payload: Arbitrary JSON-serialisable data.

        Returns:
            The written entry dict.
        """
        with self._lock:
            entry = {
                'seq': self._seq,
                'ts': time.time(),
                'type': event_type,
                'payload': payload,
                'prev_hmac': self._prev_hmac,
            }
            # compute HMAC over the canonical JSON of the entry
            canon = json.dumps(entry, sort_keys=True, separators=(',', ':'))
            entry['hmac'] = hmac.new(
                _HMAC_KEY, canon.encode(), hashlib.sha256
            ).hexdigest()

            # append
            with open(self._path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, separators=(',', ':')) + '\n')

            self._prev_hmac = entry['hmac']
            self._seq += 1
            return entry

    # ------------------------------------------------------------------
    def verify_log_integrity(self) -> bool:
        """
        Verify the entire log: check HMAC chain and individual signatures.

        Returns True if all entries are intact.
        """
        if not self._path.exists():
            return True  # empty log is valid

        prev = self.GENESIS_HMAC
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)

                    # check chain link
                    if entry.get('prev_hmac') != prev:
                        print(f"[LearningAudit] Chain break at line {lineno}")
                        return False

                    stored_hmac = entry.pop('hmac')
                    canon = json.dumps(entry, sort_keys=True, separators=(',', ':'))
                    expected = hmac.new(
                        _HMAC_KEY, canon.encode(), hashlib.sha256
                    ).hexdigest()
                    if not hmac.compare_digest(stored_hmac, expected):
                        print(f"[LearningAudit] HMAC mismatch at line {lineno}")
                        return False
                    prev = stored_hmac
            return True
        except Exception as e:
            print(f"[LearningAudit] Verification error: {e}")
            return False

    # ------------------------------------------------------------------
    def get_entries(self, limit: int = 100) -> List[dict]:
        """Return the last *limit* entries."""
        if not self._path.exists():
            return []
        entries = []
        with open(self._path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]

    def get_stats(self) -> dict:
        entries = self.get_entries(limit=999_999)
        from collections import Counter
        types = Counter(e.get('type') for e in entries)
        return {
            'total_entries': len(entries),
            'by_type': dict(types),
            'integrity_ok': self.verify_log_integrity(),
        }
