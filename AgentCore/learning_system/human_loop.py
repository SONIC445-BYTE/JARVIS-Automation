"""
Human Loop — User review, approval, and incremental training
===============================================================
Manages the approval workflow for proposed actions, adapters,
and high-risk operations.
"""

import os
import time
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from threading import Lock

from .action_discovery import ProposedAction


@dataclass
class ApprovalRecord:
    """Record of a human approval / rejection."""
    approval_id: str
    proposed_action_id: str
    decision: str  # "approved" | "rejected" | "deferred"
    comments: str = ''
    reviewer: str = 'owner'
    timestamp: float = field(default_factory=time.time)
    dry_run_result: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class HumanLoop:
    """
    Manage user reviews and approvals for proposed actions.

    Workflow:
    1. present_proposed_action() queues a proposal for review.
    2. User sees plan steps, confidence, risk, and can test-run.
    3. apply_approval() records the decision.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            root = Path(__file__).resolve().parents[2]
            storage_dir = root / 'data' / 'approvals'
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._pending: Dict[str, ProposedAction] = {}
        self._lock = Lock()
        self._load_pending()

    # ── public API ───────────────────────────────────────────

    def present_proposed_action(
        self,
        proposed: ProposedAction,
    ) -> ApprovalRecord:
        """
        Queue a proposal for human review.

        Returns an ApprovalRecord with decision='pending'.
        """
        approval_id = f"apr_{uuid.uuid4().hex[:10]}"
        with self._lock:
            self._pending[approval_id] = proposed
            self._persist_pending(approval_id, proposed)

        record = ApprovalRecord(
            approval_id=approval_id,
            proposed_action_id=proposed.id,
            decision='pending',
        )
        return record

    def get_pending_approvals(
        self,
        user_id: str = 'owner',
    ) -> List[Dict]:
        """
        Return all pending proposals for a given user.

        Returns list of dicts with approval_id, action name,
        confidence, and risk_level.
        """
        with self._lock:
            results = []
            for aid, action in self._pending.items():
                results.append({
                    'approval_id': aid,
                    'action_id': action.id,
                    'name': action.name,
                    'description': action.description,
                    'confidence': action.confidence,
                    'risk_level': action.risk_level,
                    'plan_steps': len(action.plan),
                    'created_at': action.created_at,
                })
            return results

    def apply_approval(
        self,
        approval_id: str,
        decision: str,
        comments: str = '',
    ) -> Optional[ApprovalRecord]:
        """
        Record a decision for a pending proposal.

        Args:
            approval_id: ID returned by present_proposed_action.
            decision: "approved" | "rejected" | "deferred"
            comments: Optional reviewer comments.

        Returns:
            ApprovalRecord or None if approval_id not found.
        """
        with self._lock:
            proposed = self._pending.pop(approval_id, None)
        if proposed is None:
            return None

        record = ApprovalRecord(
            approval_id=approval_id,
            proposed_action_id=proposed.id,
            decision=decision,
            comments=comments,
        )

        # Persist the decision
        self._persist_decision(record)

        # Remove pending file
        pending_file = self._dir / f"pending_{approval_id}.json"
        if pending_file.exists():
            pending_file.unlink()

        return record

    def dry_run(
        self,
        approval_id: str,
    ) -> Optional[str]:
        """
        Perform a dry-run of a pending action.

        Returns a description of what would happen (no side-effects).
        """
        with self._lock:
            proposed = self._pending.get(approval_id)
        if proposed is None:
            return None

        lines = [f"DRY RUN: {proposed.name}"]
        lines.append(f"Confidence: {proposed.confidence}")
        lines.append(f"Risk: {proposed.risk_level}")
        lines.append(f"Steps ({len(proposed.plan)}):")
        for i, step in enumerate(proposed.plan, 1):
            op = step.get('op', step.get('token', '?'))
            lines.append(f"  {i}. {op}")
        lines.append("--- (no changes made) ---")
        return '\n'.join(lines)

    # ── persistence ──────────────────────────────────────────

    def _persist_pending(self, approval_id: str, proposed: ProposedAction):
        path = self._dir / f"pending_{approval_id}.json"
        data = {
            'approval_id': approval_id,
            'proposed': proposed.to_dict(),
            'queued_at': time.time(),
        }
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _persist_decision(self, record: ApprovalRecord):
        path = self._dir / f"decision_{record.approval_id}.json"
        path.write_text(
            json.dumps(record.to_dict(), indent=2, default=str),
            encoding='utf-8',
        )

    def _load_pending(self):
        """Reload pending approvals from disk on startup."""
        for f in self._dir.glob('pending_*.json'):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                aid = data['approval_id']
                pd = data['proposed']
                proposed = ProposedAction(
                    id=pd['id'],
                    name=pd['name'],
                    description=pd['description'],
                    plan=pd['plan'],
                    confidence=pd['confidence'],
                    risk_level=pd.get('risk_level', 'standard'),
                    examples=pd.get('examples', []),
                    verification_checks=pd.get('verification_checks', []),
                    notes=pd.get('notes', ''),
                    created_by=pd.get('created_by', ''),
                    created_at=pd.get('created_at', ''),
                )
                self._pending[aid] = proposed
            except Exception:
                continue

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)
