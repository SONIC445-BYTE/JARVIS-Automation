"""
Causal Memory — Store and query cause→effect relationships
==============================================================
SQLite-backed (encrypted-at-rest via application layer).
90-day default retention, exportable, purgeable.
"""

import os
import time
import json
import sqlite3
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class EventSig:
    """Signature of a cause or effect event."""
    name: str
    context: Dict = field(default_factory=dict)

    @property
    def hash(self) -> str:
        raw = json.dumps({'n': self.name, 'c': self.context}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class CausalLink:
    """A discovered cause→effect relationship."""
    id: str
    cause_signature: str
    effect_signature: str
    context_hash: str
    confidence: float
    evidence_count: int
    last_observed: float
    notes: str = ''

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'cause_signature': self.cause_signature,
            'effect_signature': self.effect_signature,
            'context_hash': self.context_hash,
            'confidence': self.confidence,
            'evidence_count': self.evidence_count,
            'last_observed': self.last_observed,
            'notes': self.notes,
        }


class CausalMemory:
    """
    Store causal links discovered from traces and outcomes.

    Example insight:
        "Studying after midnight → drop in recall score" (p=0.72)

    Privacy:
        - All data stored locally.
        - Encryption handled at application startup if key is set.
        - 90-day default retention.
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS causal_links (
        id TEXT PRIMARY KEY,
        cause_hash TEXT NOT NULL,
        effect_hash TEXT NOT NULL,
        context_hash TEXT,
        confidence REAL DEFAULT 0.0,
        evidence_count INTEGER DEFAULT 1,
        first_observed REAL,
        last_observed REAL,
        notes TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_cause ON causal_links(cause_hash);
    CREATE INDEX IF NOT EXISTS idx_effect ON causal_links(effect_hash);
    """

    def __init__(self, db_path: Optional[str] = None,
                 retention_days: int = 90):
        if db_path is None:
            root = Path(__file__).resolve().parents[2]
            db_path = root / 'data' / 'causal_memory.sqlite'
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._retention = retention_days
        self._lock = Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.executescript(self._SCHEMA)
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    # ── public API ───────────────────────────────────────────

    def record_causal(
        self,
        cause: EventSig,
        effect: EventSig,
        context: dict,
        strength: float,
    ) -> None:
        """
        Record or update a causal link.

        If the link already exists (same cause+effect hash), its
        evidence_count and confidence are updated.
        """
        cause_h = cause.hash
        effect_h = effect.hash
        ctx_raw = json.dumps(context, sort_keys=True)
        ctx_h = hashlib.sha256(ctx_raw.encode()).hexdigest()[:16]
        link_id = f"cl:{cause_h}_{effect_h}"
        now = time.time()

        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT evidence_count, confidence FROM causal_links WHERE id=?",
                    (link_id,),
                ).fetchone()

                if row:
                    new_count = row[0] + 1
                    # Bayesian-ish update: blend old confidence with new strength
                    new_conf = (row[1] * row[0] + strength) / new_count
                    conn.execute(
                        "UPDATE causal_links SET evidence_count=?, confidence=?, "
                        "last_observed=?, context_hash=?, notes=? WHERE id=?",
                        (new_count, round(new_conf, 4), now, ctx_h,
                         f"{cause.name} → {effect.name}", link_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO causal_links "
                        "(id, cause_hash, effect_hash, context_hash, "
                        " confidence, evidence_count, first_observed, "
                        " last_observed, notes) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (link_id, cause_h, effect_h, ctx_h,
                         round(strength, 4), 1, now, now,
                         f"{cause.name} → {effect.name}"),
                    )
                conn.commit()
            finally:
                conn.close()

    def query_causes(self, effect: EventSig) -> List[CausalLink]:
        """Find all known causes for a given effect."""
        return self._query('effect_hash', effect.hash)

    def query_effects(self, cause: EventSig) -> List[CausalLink]:
        """Find all known effects of a given cause."""
        return self._query('cause_hash', cause.hash)

    # ── maintenance ──────────────────────────────────────────

    def purge_old(self, days: Optional[int] = None) -> int:
        """Delete links older than *days*. Returns count deleted."""
        days = days or self._retention
        cutoff = time.time() - days * 86400
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute(
                    "DELETE FROM causal_links WHERE last_observed < ?",
                    (cutoff,),
                )
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()

    def export_all(self) -> List[dict]:
        """Export every causal link as a list of dicts."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT id, cause_hash, effect_hash, context_hash, "
                    "confidence, evidence_count, last_observed, notes "
                    "FROM causal_links ORDER BY last_observed DESC"
                ).fetchall()
                return [
                    CausalLink(
                        id=r[0], cause_signature=r[1], effect_signature=r[2],
                        context_hash=r[3], confidence=r[4],
                        evidence_count=r[5], last_observed=r[6], notes=r[7],
                    ).to_dict()
                    for r in rows
                ]
            finally:
                conn.close()

    def purge_all(self) -> None:
        """Delete ALL causal links. Use with caution."""
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("DELETE FROM causal_links")
                conn.commit()
            finally:
                conn.close()

    def count(self) -> int:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute("SELECT COUNT(*) FROM causal_links").fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    # ── internal ─────────────────────────────────────────────

    def _query(self, column: str, hash_val: str) -> List[CausalLink]:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    f"SELECT id, cause_hash, effect_hash, context_hash, "
                    f"confidence, evidence_count, last_observed, notes "
                    f"FROM causal_links WHERE {column}=? "
                    f"ORDER BY confidence DESC",
                    (hash_val,),
                ).fetchall()
                return [
                    CausalLink(
                        id=r[0], cause_signature=r[1], effect_signature=r[2],
                        context_hash=r[3], confidence=r[4],
                        evidence_count=r[5], last_observed=r[6], notes=r[7],
                    )
                    for r in rows
                ]
            finally:
                conn.close()
