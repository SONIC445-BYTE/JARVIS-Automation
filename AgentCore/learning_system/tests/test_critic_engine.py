"""
Tests: Critic Engine
======================
Destructive plan → verdict ≠ "ok", require_confirmation.
Safe plan → verdict = "ok".
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AgentCore.learning_system.critic_engine import CriticEngine, TaskPlan


class TestCriticEngine(unittest.TestCase):

    def setUp(self):
        self.critic = CriticEngine()

    def test_destructive_plan_rejected(self):
        """A plan with 'delete' should not get verdict='ok'."""
        plan = TaskPlan(
            plan_id='test_1',
            steps=[
                {'op': 'select_all'},
                {'op': 'delete', 'target': 'Downloads/*'},
            ],
            intent_text='delete my downloads',
            risk_level='destructive',
        )
        result = self.critic.critique_plan(plan)
        self.assertNotEqual(result.verdict, 'ok')
        self.assertTrue(result.require_confirmation)
        self.assertTrue(
            any('destructive' in issue for issue in result.issues),
            "Issues should mention 'destructive'"
        )

    def test_safe_plan_ok(self):
        """A simple safe plan should get verdict='ok'."""
        plan = TaskPlan(
            plan_id='test_2',
            steps=[
                {'op': 'open_app', 'app': 'notepad'},
                {'op': 'type', 'text': 'hello'},
            ],
            intent_text='open notepad and type hello',
        )
        result = self.critic.critique_plan(plan)
        self.assertEqual(result.verdict, 'ok')
        self.assertFalse(result.require_confirmation)

    def test_privacy_plan_caution(self):
        """Sharing data should trigger caution."""
        plan = TaskPlan(
            plan_id='test_3',
            steps=[
                {'op': 'share', 'target': 'public'},
            ],
            intent_text='share my document publicly',
        )
        result = self.critic.critique_plan(plan)
        self.assertIn(result.verdict, ('caution', 'reject'))
        self.assertTrue(
            any('privacy' in issue for issue in result.issues)
        )

    def test_system_op_caution(self):
        """System operations should trigger caution."""
        plan = TaskPlan(
            plan_id='test_4',
            steps=[{'op': 'shutdown'}],
            intent_text='shut down computer',
        )
        result = self.critic.critique_plan(plan)
        self.assertNotEqual(result.verdict, 'ok')

    def test_success_probability_range(self):
        """Estimated success probability should be in [0,1]."""
        plan = TaskPlan(
            plan_id='test_5',
            steps=[{'op': 'click'}],
            intent_text='click button',
        )
        result = self.critic.critique_plan(plan)
        self.assertGreaterEqual(result.estimated_success_probability, 0.0)
        self.assertLessEqual(result.estimated_success_probability, 1.0)

    def test_alternatives_for_destructive(self):
        """Destructive plans should have alternative suggestions."""
        plan = TaskPlan(
            plan_id='test_6',
            steps=[{'op': 'erase', 'target': 'all'}],
            intent_text='erase everything',
            risk_level='destructive',
        )
        result = self.critic.critique_plan(plan)
        self.assertGreater(len(result.alternatives), 0)


if __name__ == '__main__':
    unittest.main()
