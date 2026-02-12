"""
Critic Engine — Evaluate plans for feasibility and risk
=========================================================
Provides risk assessment, conflict detection, and alternative
suggestions for multi-step task plans.
"""

import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field


# ── data models ──────────────────────────────────────────────

@dataclass
class TaskPlan:
    """A multi-step task plan to critique."""
    plan_id: str
    steps: List[Dict]
    intent_text: str = ''
    target_app: str = ''
    risk_level: str = 'standard'


@dataclass
class CritiqueResult:
    """Result of plan evaluation."""
    verdict: str  # "ok" | "caution" | "reject"
    issues: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    estimated_success_probability: float = 0.0
    require_confirmation: bool = False
    explanation: str = ''

    def to_dict(self) -> dict:
        return {
            'verdict': self.verdict,
            'issues': self.issues,
            'alternatives': self.alternatives,
            'estimated_success_probability': self.estimated_success_probability,
            'require_confirmation': self.require_confirmation,
            'explanation': self.explanation,
        }


# ── destructive / risky operations ──────────────────────────

_DESTRUCTIVE_OPS = {
    'delete', 'remove', 'erase', 'wipe', 'format', 'drop',
    'uninstall', 'purge', 'clear', 'destroy', 'truncate',
    'overwrite', 'reset',
}

_PRIVACY_OPS = {
    'share', 'post', 'publish', 'send', 'broadcast',
    'export', 'upload', 'email', 'forward',
}

_SYSTEM_OPS = {
    'shutdown', 'restart', 'reboot', 'kill', 'terminate',
    'install', 'update', 'upgrade',
}


# ── main class ───────────────────────────────────────────────

class CriticEngine:
    """
    Evaluate planned multi-step tasks for feasibility,
    conflicts, resource/time cost, and long-term impact.
    """

    def critique_plan(
        self,
        plan: TaskPlan,
        user_profile: Optional[dict] = None,
    ) -> CritiqueResult:
        """
        Analyse a plan and return verdict + issues + alternatives.

        Args:
            plan: The TaskPlan to evaluate.
            user_profile: Optional user context (permissions, prefs).

        Returns:
            CritiqueResult with verdict, issues, and suggestions.
        """
        issues: List[str] = []
        alternatives: List[str] = []
        is_destructive = False
        is_privacy_sensitive = False
        is_system_op = False
        step_count = len(plan.steps)

        for step in plan.steps:
            op = self._get_op(step).lower()

            # Check destructive
            if any(d in op for d in _DESTRUCTIVE_OPS):
                is_destructive = True
                issues.append(f"destructive: step '{op}' is irreversible")

            # Check privacy
            if any(p in op for p in _PRIVACY_OPS):
                is_privacy_sensitive = True
                issues.append(f"privacy: step '{op}' may expose data")

            # Check system
            if any(s in op for s in _SYSTEM_OPS):
                is_system_op = True
                issues.append(f"system: step '{op}' affects system state")

        # Check plan-level risks
        if step_count > 10:
            issues.append(f"complexity: plan has {step_count} steps (high)")

        if plan.risk_level == 'destructive' or is_destructive:
            issues.append("destructive: plan involves irreversible operations")
            alternatives.append("Archive or back up before proceeding")
            alternatives.append("Run in dry-run mode first")

        if is_privacy_sensitive:
            alternatives.append("Review data before sharing externally")

        # Compute success probability
        base_prob = 0.90
        if is_destructive:
            base_prob -= 0.30
        if is_system_op:
            base_prob -= 0.15
        if step_count > 10:
            base_prob -= 0.10
        if step_count > 20:
            base_prob -= 0.15
        success_prob = max(0.05, min(1.0, base_prob))

        # Determine verdict
        if is_destructive:
            verdict = 'reject'
            require_confirmation = True
        elif len(issues) >= 3 or is_system_op:
            verdict = 'caution'
            require_confirmation = True
        elif len(issues) >= 1:
            verdict = 'caution'
            require_confirmation = False
        else:
            verdict = 'ok'
            require_confirmation = False

        explanation = self._build_explanation(
            verdict, issues, alternatives, success_prob
        )

        return CritiqueResult(
            verdict=verdict,
            issues=issues,
            alternatives=alternatives,
            estimated_success_probability=round(success_prob, 2),
            require_confirmation=require_confirmation,
            explanation=explanation,
        )

    # ── LLM-based critique (optional, for future use) ────────

    def critique_with_llm(
        self,
        plan: TaskPlan,
        llm_fn=None,
    ) -> Optional[CritiqueResult]:
        """
        Use a local LLM to provide a richer critique.

        Args:
            plan: The plan to evaluate.
            llm_fn: Callable that accepts a prompt string and
                     returns a response string.

        Returns:
            CritiqueResult or None if LLM unavailable.
        """
        if llm_fn is None:
            return None

        prompt = self._build_critic_prompt(plan)
        try:
            response = llm_fn(prompt)
            return self._parse_llm_critique(response)
        except Exception:
            return None

    # ── internal ─────────────────────────────────────────────

    @staticmethod
    def _get_op(step: dict) -> str:
        """Extract operation name from a step dict."""
        return (step.get('op', '')
                or step.get('action', '')
                or step.get('action_type', '')
                or step.get('token', '')
                or str(step))

    @staticmethod
    def _build_explanation(
        verdict: str,
        issues: List[str],
        alternatives: List[str],
        prob: float,
    ) -> str:
        parts = [f"Verdict: {verdict.upper()} (success probability: {prob:.0%})"]
        if issues:
            parts.append("Issues: " + "; ".join(issues))
        if alternatives:
            parts.append("Suggestions: " + "; ".join(alternatives))
        return ". ".join(parts)

    @staticmethod
    def _build_critic_prompt(plan: TaskPlan) -> str:
        steps_str = '\n'.join(
            f"  {i+1}. {s}" for i, s in enumerate(plan.steps)
        )
        return (
            "You are Jarvis-Critic. Evaluate this plan for safety, "
            "time, and success probability.\n\n"
            f"Intent: {plan.intent_text}\n"
            f"Steps:\n{steps_str}\n\n"
            "List problems, score success (0-1), propose 1-3 alternatives, "
            "and suggest confirming questions. Only use context provided."
        )

    @staticmethod
    def _parse_llm_critique(response: str) -> CritiqueResult:
        """Best-effort parse of LLM response into CritiqueResult."""
        response_l = response.lower()
        issues = []
        alternatives = []

        if 'destructive' in response_l or 'irreversible' in response_l:
            issues.append('destructive')
        if 'privacy' in response_l:
            issues.append('privacy concern')
        if 'conflict' in response_l:
            issues.append('potential conflict')

        # Simple verdict inference
        if 'reject' in response_l or 'do not proceed' in response_l:
            verdict = 'reject'
        elif 'caution' in response_l or 'warning' in response_l:
            verdict = 'caution'
        else:
            verdict = 'ok'

        return CritiqueResult(
            verdict=verdict,
            issues=issues,
            alternatives=alternatives,
            estimated_success_probability=0.5,
            require_confirmation=verdict != 'ok',
            explanation=response[:500],
        )
