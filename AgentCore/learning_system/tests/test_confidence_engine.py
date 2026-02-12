"""
Tests: Confidence Engine
==========================
Known inputs → expected score within ±0.05.
Destructive penalty reduces score below thresholds.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AgentCore.learning_system.confidence_engine import (
    ConfidenceEngine, ActionCandidate, Step,
)


class TestConfidenceEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ConfidenceEngine()

    def test_known_input_high(self):
        """freq=10, success=0.9 → expected ~0.769+0.36 ≈ 1.0 (clamped)."""
        c = ActionCandidate(
            steps=[], frequency=10, success_rate=0.9,
        )
        score = self.engine.score_action(c)
        # base = 10/13 ≈ 0.769, bonus = 0.9*0.4 = 0.36 → 1.0 clamped
        self.assertAlmostEqual(score, 1.0, delta=0.05)

    def test_known_input_low(self):
        """freq=1, success=0.5 → base=0.25, bonus=0.2 → ~0.45."""
        c = ActionCandidate(
            steps=[], frequency=1, success_rate=0.5,
        )
        score = self.engine.score_action(c)
        expected = 0.25 + 0.20  # 0.45
        self.assertAlmostEqual(score, expected, delta=0.05)

    def test_zero_frequency(self):
        """freq=0 → base=0, bonus=0 → 0."""
        c = ActionCandidate(steps=[], frequency=0, success_rate=0.0)
        score = self.engine.score_action(c)
        self.assertAlmostEqual(score, 0.0, delta=0.05)

    def test_destructive_penalty(self):
        """Destructive flag subtracts 0.5."""
        c = ActionCandidate(
            steps=[], frequency=5, success_rate=0.8,
            is_destructive=True,
        )
        score = self.engine.score_action(c)
        # base = 5/8 = 0.625, bonus = 0.32, penalty = 0.5 → 0.445
        self.assertLess(score, 0.50)

    def test_destructive_below_auto_threshold(self):
        """Destructive actions should never reach 0.92."""
        c = ActionCandidate(
            steps=[], frequency=100, success_rate=1.0,
            is_destructive=True,
        )
        score = self.engine.score_action(c)
        self.assertLess(score, 0.92)

    def test_context_match(self):
        """Context similarity adds to score."""
        c = ActionCandidate(steps=[], frequency=5, success_rate=0.8)
        base_score = self.engine.score_action(c, context_similarity=0.0)
        ctx_score = self.engine.score_action(c, context_similarity=1.0)
        self.assertGreater(ctx_score, base_score)

    def test_score_plan(self):
        """Plan with destructive step triggers penalty."""
        steps = [
            Step(op='open_app'),
            Step(op='delete', is_destructive=True),
        ]
        score = self.engine.score_plan(steps, frequency=5, success_rate=0.9)
        self.assertLess(score, 0.92)

    def test_score_plan_safe(self):
        """Plan with no destructive steps gets full score."""
        steps = [
            Step(op='open_app'),
            Step(op='click'),
        ]
        score = self.engine.score_plan(steps, frequency=10, success_rate=0.9)
        self.assertGreater(score, 0.7)


if __name__ == '__main__':
    unittest.main()
