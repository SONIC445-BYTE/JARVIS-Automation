"""
Tests: Causal Memory
======================
Record cause→effect pairs and verify confidence builds up.
Also test export and purge.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AgentCore.learning_system.causal_memory import CausalMemory, EventSig


class TestCausalMemory(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, 'test_causal.sqlite')
        self.mem = CausalMemory(db_path=self.db_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_record_and_query(self):
        """Record a single causal link and query it back."""
        cause = EventSig(name='study_after_midnight')
        effect = EventSig(name='low_recall_next_day')
        self.mem.record_causal(cause, effect, {}, strength=0.7)

        results = self.mem.query_causes(effect)
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0].confidence, 0.7, delta=0.01)

    def test_confidence_builds_with_evidence(self):
        """10 recordings with strength 0.75 → confidence ≥ 0.7."""
        cause = EventSig(name='study_after_midnight')
        effect = EventSig(name='low_recall_next_day')

        for _ in range(10):
            self.mem.record_causal(cause, effect, {'time': 'night'}, strength=0.75)

        results = self.mem.query_causes(effect)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].evidence_count, 10)
        self.assertGreaterEqual(results[0].confidence, 0.7)

    def test_query_effects(self):
        """Query effects of a given cause."""
        cause = EventSig(name='late_sleep')
        effect1 = EventSig(name='grogginess')
        effect2 = EventSig(name='low_focus')

        self.mem.record_causal(cause, effect1, {}, strength=0.8)
        self.mem.record_causal(cause, effect2, {}, strength=0.6)

        results = self.mem.query_effects(cause)
        self.assertEqual(len(results), 2)

    def test_export_all(self):
        """Export returns all links."""
        cause = EventSig(name='a')
        effect = EventSig(name='b')
        self.mem.record_causal(cause, effect, {}, strength=0.5)

        exported = self.mem.export_all()
        self.assertEqual(len(exported), 1)
        self.assertIn('cause_signature', exported[0])

    def test_purge_all(self):
        """Purge removes everything."""
        cause = EventSig(name='x')
        effect = EventSig(name='y')
        self.mem.record_causal(cause, effect, {}, strength=0.5)
        self.assertEqual(self.mem.count(), 1)

        self.mem.purge_all()
        self.assertEqual(self.mem.count(), 0)

    def test_count(self):
        self.assertEqual(self.mem.count(), 0)
        cause = EventSig(name='a')
        effect = EventSig(name='b')
        self.mem.record_causal(cause, effect, {}, strength=0.5)
        self.assertEqual(self.mem.count(), 1)


if __name__ == '__main__':
    unittest.main()
