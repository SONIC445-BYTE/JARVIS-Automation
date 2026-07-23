"""
Phase 3a: persistent cross-session memory -- storage layer + minimal
read/write API. Groundwork only, per the phasing brief: NOT wired into
the conversation loop's response generation yet, and NOT importable
from anywhere in the resolution/routing path (enforced by
tests/test_session_memory_boundary.py, not just documented -- see
docs/phase3_hermes_capabilities.md).

Wraps the existing AgentCore/memory_store.py's MemoryStore rather than
building a new store: MemoryStore already exists, is local-only, and
covers exactly the key/value + category shape this needs. It was
previously unreachable from the live path (only feedback_engine.py/
optimizer.py imported it, and nothing imports either of those) --
this is its first live consumer.

Two deliberate departures from MemoryStore's defaults, both explained
in the design doc:
- store_dir redirected to state/memory (the same gitignored runtime-
  state directory onboarding.py's first-run marker uses), not
  MemoryStore's own default data/memory -- that directory exists on
  disk but is untracked AND not covered by .gitignore, a real risk for
  data that shouldn't end up in a commit.
- MemoryStore's "encryption" (XOR with a hardcoded default key) is not
  real confidentiality -- used as-is here (no new crypto invented in
  this pass) but not represented as protection anywhere in this
  module's own API or docs.

Boundary this module must never cross: memory can inform response tone,
TTS preferences, and which shortcut to suggest first. It must NEVER be
read by AgentCore/resolution_gate.py or AgentCore/command_router.py to
skip or weaken a confirmation step -- "they usually say yes" must never
become an auto-yes. Enforced by keeping this module unimported by
either of those, verified in CI by the boundary test.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .memory_store import MemoryStore

_PATTERN_PREFIX = "pattern:"
_SESSION_PREFIX = "session:"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionMemory:
    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or MemoryStore(store_dir=Path("state") / "memory")

    # ============ Preferences ============

    def get_preference(self, key: str, default=None):
        return self._store.get_pref(key, default)

    def set_preference(self, key: str, value) -> None:
        self._store.set_pref(key, value)

    # ============ Recurring command patterns ============

    def record_command_pattern(self, pattern_key: str) -> None:
        """pattern_key should be a normalized shape (e.g.
        "whatsapp_desktop.send_message" -- adapter+action), never raw
        command text, which may contain names or message content this
        module has no business retaining verbatim."""
        key = f"{_PATTERN_PREFIX}{pattern_key}"
        current = self._store.get(key, 0)
        self._store.set(key, current + 1, category="pattern")

    def top_command_patterns(self, limit: int = 5) -> List[Tuple[str, int]]:
        counts: Dict[str, int] = self._store.get_by_category("pattern")
        pairs = [
            (key[len(_PATTERN_PREFIX):], count)
            for key, count in counts.items()
            if key.startswith(_PATTERN_PREFIX)
        ]
        pairs.sort(key=lambda kv: kv[1], reverse=True)
        return pairs[:limit]

    # ============ Prior session context ============

    def start_session(self) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._store.set(
            f"{_SESSION_PREFIX}{session_id}",
            {"started_at": _now_iso(), "ended_at": None, "summary": None},
            category="session",
        )
        return session_id

    def end_session(self, session_id: str, summary: str) -> None:
        key = f"{_SESSION_PREFIX}{session_id}"
        record = self._store.get(key)
        if record is None:
            return  # unknown session id -- nothing to end, not an error
        record = dict(record)
        record["ended_at"] = _now_iso()
        record["summary"] = summary
        self._store.set(key, record, category="session")

    def recent_sessions(self, limit: int = 5) -> List[dict]:
        sessions: Dict[str, dict] = self._store.get_by_category("session")
        ordered = sorted(
            sessions.values(),
            key=lambda s: s.get("started_at") or "",
            reverse=True,
        )
        return ordered[:limit]
