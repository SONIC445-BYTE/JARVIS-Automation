"""
Tests: Action Discovery
=========================
Simulated traces → repeated sequences found → valid ProposedAction JSON.
"""

import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AgentCore.learning_system.flow_instrumentation import TraceSummary, TraceEvent
from AgentCore.learning_system.action_discovery import ActionDiscovery, ProposedAction


def _make_trace(session_id: str, events_data: list) -> TraceSummary:
    """Helper to build a TraceSummary from raw event dicts."""
    events = [
        TraceEvent(
            timestamp=time.time(),
            type=e.get('type', 'ui_click'),
            payload=e.get('payload', {}),
        )
        for e in events_data
    ]
    return TraceSummary(
        session_id=session_id,
        start_time=time.time() - 60,
        end_time=time.time(),
        events=events,
        app_context='WhatsApp',
        event_count=len(events),
    )


# The repeated sequence: open_app → click clip → click gallery_top_right → send
_REPEATED_EVENTS = [
    {'type': 'ui_open',  'payload': {'app': 'WhatsApp'}},
    {'type': 'ui_click', 'payload': {'app': 'WhatsApp', 'ui_node': {'text': 'clip', 'role': 'button'}}},
    {'type': 'ui_click', 'payload': {'app': 'WhatsApp', 'ui_node': {'text': 'gallery_top_right', 'role': 'image'}}},
    {'type': 'ui_click', 'payload': {'app': 'WhatsApp', 'ui_node': {'text': 'send', 'role': 'button'}}},
]


class TestActionDiscovery(unittest.TestCase):

    def test_find_repeated_sequences_with_5_traces(self):
        """5 identical traces → at least 1 candidate with occurrences ≥ 3."""
        traces = [_make_trace(f"s{i}", _REPEATED_EVENTS) for i in range(5)]
        discovery = ActionDiscovery(min_occurrences=3)
        candidates = discovery.find_repeated_sequences(traces)
        self.assertGreaterEqual(len(candidates), 1)
        self.assertGreaterEqual(candidates[0].frequency, 3)

    def test_no_candidates_below_threshold(self):
        """2 traces (below min 3) → no candidates."""
        traces = [_make_trace(f"s{i}", _REPEATED_EVENTS) for i in range(2)]
        discovery = ActionDiscovery(min_occurrences=3)
        candidates = discovery.find_repeated_sequences(traces)
        self.assertEqual(len(candidates), 0)

    def test_propose_action_valid_json(self):
        """ProposedAction should serialise to valid JSON with required fields."""
        traces = [_make_trace(f"s{i}", _REPEATED_EVENTS) for i in range(5)]
        discovery = ActionDiscovery(min_occurrences=3)
        candidates = discovery.find_repeated_sequences(traces)
        self.assertGreaterEqual(len(candidates), 1)

        proposed = discovery.propose_action(candidates[0])
        self.assertIsInstance(proposed, ProposedAction)

        d = proposed.to_dict()
        # Schema checks
        self.assertIn('id', d)
        self.assertIn('name', d)
        self.assertIn('plan', d)
        self.assertIn('confidence', d)
        self.assertIn('risk_level', d)
        self.assertIsInstance(d['plan'], list)
        self.assertIsInstance(d['confidence'], float)
        self.assertGreaterEqual(d['confidence'], 0.0)
        self.assertLessEqual(d['confidence'], 1.0)

    def test_proposed_action_json_string(self):
        """to_json() returns parseable JSON."""
        import json
        proposed = ProposedAction(
            id='auto:test', name='test', description='d',
            plan=[{'op': 'click'}], confidence=0.8,
        )
        parsed = json.loads(proposed.to_json())
        self.assertEqual(parsed['id'], 'auto:test')


if __name__ == '__main__':
    unittest.main()
