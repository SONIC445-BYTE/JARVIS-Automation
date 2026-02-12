"""
Tests: Intent Graph
=====================
20 sample sentences → ≥ 90% correct classification.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AgentCore.learning_system.intent_graph import IntentGraph


# (input_text, expected_type)
_SAMPLES = [
    # -- commands (10) --
    ("open notepad", "command"),
    ("close chrome", "command"),
    ("send a message", "command"),
    ("launch spotify", "command"),
    ("delete that file", "command"),
    ("upload the photo", "command"),
    ("download the report", "command"),
    ("search for cats", "command"),
    ("play music", "command"),
    ("navigate to settings", "command"),
    # -- goals (5) --
    ("help me prepare for the meeting", "goal"),
    ("organize my photos from last trip", "goal"),
    ("plan a birthday party for next Saturday", "goal"),
    ("summarize the research paper", "goal"),
    ("draft an email to the team", "goal"),
    # -- questions (3) --
    ("what time is it in Tokyo?", "question"),
    ("how do I reset my password?", "question"),
    ("who is the president of France?", "question"),
    # -- smalltalk (2) --
    ("hello", "smalltalk"),
    ("thanks", "smalltalk"),
]


class TestIntentGraph(unittest.TestCase):

    def setUp(self):
        self.graph = IntentGraph(log_dir='/tmp/test_intent_logs')

    def test_classification_accuracy(self):
        """≥90% of 20 samples must be classified correctly."""
        correct = 0
        errors = []
        for text, expected in _SAMPLES:
            node = self.graph.classify_intent(text)
            if node.intent_type == expected:
                correct += 1
            else:
                errors.append(
                    f"  '{text}': expected={expected}, got={node.intent_type}"
                )

        accuracy = correct / len(_SAMPLES)
        self.assertGreaterEqual(
            accuracy, 0.90,
            f"Accuracy {accuracy:.0%} < 90%. Misclassified:\n"
            + "\n".join(errors),
        )

    def test_command_returns_slots(self):
        """Command classification should extract verb + target slots."""
        node = self.graph.classify_intent("open notepad")
        self.assertEqual(node.intent_type, "command")
        self.assertIn('verb', node.slots)
        self.assertEqual(node.slots['verb'], 'open')

    def test_goal_urgency(self):
        """Urgent phrasing should set urgency=high."""
        node = self.graph.classify_intent("help me now urgently prepare")
        self.assertEqual(node.urgency, 'high')

    def test_confidence_above_zero(self):
        """Every classification should have confidence > 0."""
        for text, _ in _SAMPLES:
            node = self.graph.classify_intent(text)
            self.assertGreater(node.confidence, 0.0)


if __name__ == '__main__':
    unittest.main()
