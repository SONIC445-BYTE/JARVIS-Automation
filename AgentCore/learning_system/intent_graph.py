"""
Intent Graph — Separate intent (why) from command (what)
==========================================================
Hybrid classifier: rule-based first, then optional local LLM.
Builds a graph of user goals → sub-goals → action templates.
"""

import re
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .pattern_extractor import ActionTemplate


# ── data models ──────────────────────────────────────────────

@dataclass
class IntentNode:
    """A classified intent."""
    id: str
    text: str
    intent_type: str  # "command" | "goal" | "question" | "smalltalk"
    urgency: str = 'normal'  # low | normal | high | critical
    success_metrics: List[str] = field(default_factory=list)
    confidence: float = 1.0
    slots: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── classification rules ─────────────────────────────────────

# Imperative verb patterns → command
_COMMAND_PATTERNS = [
    re.compile(r'^(open|start|close|launch|send|upload|download'
               r'|delete|remove|copy|move|paste|save|print'
               r'|click|type|press|scroll|select|search|play'
               r'|pause|stop|mute|unmute|maximize|minimize'
               r'|switch|navigate|go\s+to|run|execute)\b', re.I),
]

# Goal-oriented patterns → goal
_GOAL_PATTERNS = [
    re.compile(r'\b(help\s+me|prepare|organize|plan|summarize'
               r'|remind|schedule|create\s+a\s+plan|set\s+up'
               r'|figure\s+out|find\s+a\s+way|make\s+sure'
               r'|arrange|draft|compose|build|design)\b', re.I),
]

# Question patterns → question
_QUESTION_PATTERNS = [
    re.compile(r'^(what|who|where|when|why|how|is|are|do|does'
               r'|can|could|would|should|will|did)\b', re.I),
    re.compile(r'\?\s*$'),
]

# Smalltalk
_SMALLTALK_PATTERNS = [
    re.compile(r'^(hi|hello|hey|good\s+(morning|afternoon|evening)'
               r'|thanks|thank\s+you|bye|goodbye|ok|okay'
               r'|yes|no|sure|cool|nice)\s*$', re.I),
]


# ── main class ───────────────────────────────────────────────

class IntentGraph:
    """
    Classify intents and map them to action templates.

    Uses a hybrid approach:
    1. Rule-based pattern matching (fast, offline).
    2. Optional local LLM for ambiguous/long-form intents.
    """

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            root = Path(__file__).resolve().parents[2]
            log_dir = root / 'data' / 'intent_logs'
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._templates: Dict[str, ActionTemplate] = {}
        self._intent_counter = 0

    # ── public API ───────────────────────────────────────────

    def classify_intent(self, text: str) -> IntentNode:
        """
        Classify a user utterance into command / goal / question / smalltalk.

        Rule-based first; falls back to heuristic scoring for
        ambiguous input.
        """
        text_clean = text.strip()
        self._intent_counter += 1
        intent_id = f"intent_{self._intent_counter}"

        # 1. Smalltalk (exact match, highest priority)
        for pat in _SMALLTALK_PATTERNS:
            if pat.search(text_clean):
                node = IntentNode(
                    id=intent_id, text=text_clean,
                    intent_type='smalltalk', confidence=0.95,
                )
                self._log(node)
                return node

        # 2. Command (imperative verb at start)
        for pat in _COMMAND_PATTERNS:
            m = pat.search(text_clean)
            if m:
                slots = self._extract_command_slots(text_clean, m.group(1))
                node = IntentNode(
                    id=intent_id, text=text_clean,
                    intent_type='command', confidence=0.90,
                    slots=slots,
                )
                self._log(node)
                return node

        # 3. Question
        for pat in _QUESTION_PATTERNS:
            if pat.search(text_clean):
                node = IntentNode(
                    id=intent_id, text=text_clean,
                    intent_type='question', confidence=0.85,
                )
                self._log(node)
                return node

        # 4. Goal-oriented
        for pat in _GOAL_PATTERNS:
            if pat.search(text_clean):
                node = IntentNode(
                    id=intent_id, text=text_clean,
                    intent_type='goal', confidence=0.80,
                    urgency=self._infer_urgency(text_clean),
                )
                self._log(node)
                return node

        # 5. Fallback: classify by length heuristic
        if len(text_clean.split()) <= 4:
            itype = 'command'
            conf = 0.60
        else:
            itype = 'goal'
            conf = 0.55

        node = IntentNode(
            id=intent_id, text=text_clean,
            intent_type=itype, confidence=conf,
        )
        self._log(node)
        return node

    def map_intent_to_actions(
        self,
        intent: IntentNode,
    ) -> List[Tuple[ActionTemplate, float]]:
        """
        Map an IntentNode to candidate ActionTemplates.

        Returns list of (template, score) sorted descending.
        """
        results = []
        text_lower = intent.text.lower()
        for tid, tmpl in self._templates.items():
            # Simple keyword overlap scoring
            tmpl_words = set(tmpl.name.lower().replace('_', ' ').split())
            intent_words = set(text_lower.split())
            overlap = len(tmpl_words & intent_words)
            if overlap > 0:
                score = min(1.0, overlap / max(len(tmpl_words), 1))
                results.append((tmpl, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def register_template(self, template: ActionTemplate) -> None:
        """Register an ActionTemplate for intent mapping."""
        self._templates[template.template_id] = template

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _extract_command_slots(text: str, verb: str) -> dict:
        """Extract basic slots from a command utterance."""
        remainder = text[len(verb):].strip()
        slots = {'verb': verb.lower()}
        if remainder:
            slots['target'] = remainder
        return slots

    @staticmethod
    def _infer_urgency(text: str) -> str:
        text_l = text.lower()
        if any(w in text_l for w in ['urgent', 'asap', 'immediately', 'now', 'critical']):
            return 'high'
        if any(w in text_l for w in ['later', 'sometime', 'when you can', 'no rush']):
            return 'low'
        return 'normal'

    def _log(self, node: IntentNode) -> None:
        """Persist classification result for future tuning."""
        try:
            log_file = self._log_dir / f"intents_{time.strftime('%Y%m%d')}.jsonl"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(node.to_dict(), default=str) + '\n')
        except Exception:
            pass  # non-critical
