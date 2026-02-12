"""
Action Discovery — Find repeated sequences in traces
======================================================
Analyses interaction traces to surface repeated multi-step
actions that can be automated.

Algorithm:
1. Collect traces for N days or M examples.
2. Extract atomic events and normalise.
3. Frequent subsequence mining (simplified PrefixSpan).
4. Cluster by similarity + generalise.
5. Score via ConfidenceEngine.
6. Propose actions (≥3 occurrences, confidence ≥0.6).
"""

import time
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

from .flow_instrumentation import TraceSummary, TraceEvent
from .confidence_engine import ConfidenceEngine, ActionCandidate
from .pattern_extractor import PatternExtractor, Sequence


# ── data models ──────────────────────────────────────────────

@dataclass
class ProposedAction:
    """A proposed automation ready for human review."""
    id: str
    name: str
    description: str
    plan: List[Dict]
    confidence: float
    examples: List[str] = field(default_factory=list)
    risk_level: str = 'standard'
    verification_checks: List[str] = field(default_factory=list)
    notes: str = ''
    created_by: str = 'action_discovery_v1'
    created_at: str = ''

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ── main class ───────────────────────────────────────────────

class ActionDiscovery:
    """Discover repeated action patterns from traces."""

    def __init__(self,
                 min_occurrences: int = 3,
                 min_confidence: float = 0.6,
                 templates_dir: Optional[str] = None):
        self._min_occ = min_occurrences
        self._min_conf = min_confidence
        self._confidence = ConfidenceEngine()
        self._extractor = PatternExtractor()
        if templates_dir is None:
            root = Path(__file__).resolve().parents[2]
            templates_dir = root / 'data' / 'action_templates'
        self._templates_dir = Path(templates_dir)
        self._templates_dir.mkdir(parents=True, exist_ok=True)

    # ── public API ───────────────────────────────────────────

    def find_repeated_sequences(
        self,
        traces: List[TraceSummary],
        min_occurrences: Optional[int] = None,
    ) -> List[ActionCandidate]:
        """
        Analyse traces and return candidates with sufficient
        occurrences.

        Args:
            traces: List of completed traces.
            min_occurrences: Override default minimum.

        Returns:
            List of ActionCandidate objects.
        """
        min_occ = min_occurrences or self._min_occ

        # 1. Extract token sequences from each trace
        sequences = self._traces_to_sequences(traces)

        # 2. Cluster similar sequences
        clusters = self._extractor.cluster_sequences(sequences)

        # 3. Filter by minimum occurrences
        candidates: List[ActionCandidate] = []
        for cluster in clusters:
            if cluster.size < min_occ:
                continue

            # Build candidate from cluster
            steps = [{'token': t} for t in (cluster.representative or [])]
            contexts = [s.context for s in cluster.sequences if s.context]

            candidate = ActionCandidate(
                steps=steps,
                contexts=contexts,
                frequency=cluster.size,
                success_rate=1.0,  # assume success unless told otherwise
                last_occurrence=max(
                    (s.context.get('end_time', 0) for s in cluster.sequences),
                    default=0,
                ),
            )
            candidate._cluster = cluster  # keep reference for later
            candidates.append(candidate)

        return candidates

    def propose_action(self, candidate: ActionCandidate) -> ProposedAction:
        """
        Convert a candidate into a ProposedAction with
        confidence score and risk assessment.
        """
        score = self._confidence.score_action(candidate)

        # Determine risk
        risk = 'destructive' if candidate.is_destructive else 'standard'

        # Generalise into a template
        cluster = getattr(candidate, '_cluster', None)
        if cluster:
            template = self._extractor.generalize_cluster(cluster)
            plan = template.steps
            name = template.name
            desc = template.description
        else:
            plan = candidate.steps
            name = f"auto_action_{uuid.uuid4().hex[:8]}"
            desc = f"Discovered action ({candidate.frequency} occurrences)"

        return ProposedAction(
            id=f"auto:{name}",
            name=name,
            description=desc,
            plan=plan,
            confidence=round(score, 4),
            risk_level=risk,
            verification_checks=self._infer_checks(plan),
            notes=f"Observed {candidate.frequency} times",
        )

    def export_proposed_action(self, proposed: ProposedAction) -> str:
        """Write ProposedAction JSON to data/action_templates/ and return path."""
        fname = f"{proposed.id.replace(':', '_')}.json"
        path = self._templates_dir / fname
        path.write_text(proposed.to_json(), encoding='utf-8')
        return str(path)

    # ── internal ─────────────────────────────────────────────

    def _traces_to_sequences(self, traces: List[TraceSummary]) -> List[Sequence]:
        """Convert traces into normalised token sequences."""
        seqs: List[Sequence] = []
        for trace in traces:
            tokens = []
            for evt in trace.events:
                token = self._event_to_token(evt)
                if token:
                    tokens.append(token)
            if tokens:
                seqs.append(Sequence(
                    tokens=tokens,
                    context={
                        'app': trace.app_context,
                        'end_time': trace.end_time,
                    },
                    source_session=trace.session_id,
                ))
        return seqs

    @staticmethod
    def _event_to_token(event: TraceEvent) -> Optional[str]:
        """Normalise an event into a hashable token string."""
        payload = event.payload or {}
        parts = [event.type]
        if 'app' in payload:
            parts.append(payload['app'].lower().replace(' ', '_'))
        ui = payload.get('ui_node', {})
        if isinstance(ui, dict):
            role = ui.get('role', '')
            text = ui.get('text', '')
            if role:
                parts.append(role)
            if text:
                parts.append(text.lower().replace(' ', '_'))
        return ':'.join(parts) if parts else None

    @staticmethod
    def _infer_checks(plan: List[Dict]) -> List[str]:
        """Generate basic verification checks from a plan."""
        checks = []
        for step in plan:
            op = step.get('op', '')
            if op in ('open_app', 'ui_open'):
                checks.append(f"app_window_visible")
            elif op in ('click', 'ui_click'):
                checks.append(f"element_present")
        return list(dict.fromkeys(checks))  # deduplicate
