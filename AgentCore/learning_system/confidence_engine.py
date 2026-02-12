"""
Confidence Engine — Score actions, plans, and candidates
==========================================================
Algorithm:
    base   = min(1.0, frequency / (frequency + 3))
    bonus  = observed_success_rate * 0.4
    ctx    = context_similarity * 0.2
    penalty= -0.5 if destructive
    final  = clamp(base + bonus + ctx - penalty, 0, 1)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class ActionCandidate:
    """Candidate action discovered from traces."""
    steps: List[dict]
    contexts: List[dict] = None
    frequency: int = 0
    success_rate: float = 0.0
    last_occurrence: float = 0.0
    is_destructive: bool = False

    def __post_init__(self):
        if self.contexts is None:
            self.contexts = []


@dataclass
class Step:
    """Single step in a plan."""
    op: str
    args: dict = None
    is_destructive: bool = False

    def __post_init__(self):
        if self.args is None:
            self.args = {}


class ConfidenceEngine:
    """Score discovered actions and multi-step plans."""

    def __init__(self, context_weight: float = 0.2,
                 success_weight: float = 0.4,
                 destructive_penalty: float = 0.5):
        self._ctx_w = context_weight
        self._suc_w = success_weight
        self._destr_p = destructive_penalty

    def score_action(self, candidate: ActionCandidate,
                     context_similarity: float = 0.0) -> float:
        """
        Score an ActionCandidate.

        Args:
            candidate: The action candidate to score.
            context_similarity: 0-1 score of how well the current
                                context matches the candidate's contexts.

        Returns:
            Confidence score in [0, 1].
        """
        base = min(1.0, candidate.frequency / (candidate.frequency + 3))
        bonus = candidate.success_rate * self._suc_w
        ctx = context_similarity * self._ctx_w
        penalty = self._destr_p if candidate.is_destructive else 0.0
        return _clamp(base + bonus + ctx - penalty)

    def score_plan(self, plan: List[Step],
                   frequency: int = 1,
                   success_rate: float = 1.0,
                   context_similarity: float = 0.0) -> float:
        """
        Score a multi-step plan.

        Any single destructive step in the plan triggers the penalty.
        """
        is_destructive = any(s.is_destructive for s in plan)
        candidate = ActionCandidate(
            steps=[],
            frequency=frequency,
            success_rate=success_rate,
            is_destructive=is_destructive,
        )
        return self.score_action(candidate, context_similarity)

    def meets_threshold(self, score: float, threshold: float) -> bool:
        """Convenience check."""
        return score >= threshold
