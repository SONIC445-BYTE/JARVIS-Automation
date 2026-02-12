"""
Tests: Feature Gate
=====================
Verify default-OFF behaviour and spoil test
(adapters cannot execute with flag OFF).
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AgentCore.learning_system.feature_gate import FeatureGate


class TestFeatureGateDefaults(unittest.TestCase):
    """All flags must default to OFF."""

    def setUp(self):
        # Point at a non-existent file so defaults apply
        self.gate = FeatureGate(config_path='/tmp/__nonexistent__.yaml')

    def test_master_disabled(self):
        self.assertFalse(self.gate.enabled('learning_system'))

    def test_all_modules_disabled(self):
        modules = [
            'flow_instrumentation', 'action_discovery',
            'pattern_extractor', 'adapter_generator',
            'adapter_generation', 'confidence_engine',
            'intent_graph', 'critic_engine',
            'causal_memory', 'human_loop', 'audit_log',
        ]
        for mod in modules:
            self.assertFalse(
                self.gate.enabled(mod),
                f"{mod} should be disabled by default",
            )

    def test_shadow_mode_default(self):
        self.assertTrue(self.gate.get('shadow_mode', True))


class TestFeatureGateWithConfig(unittest.TestCase):
    """Test loading from a YAML file."""

    def test_load_enabled(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write("enabled: true\naction_discovery: true\n")
            f.flush()
            gate = FeatureGate(config_path=f.name)

        self.assertTrue(gate.enabled('learning_system'))
        self.assertTrue(gate.enabled('action_discovery'))
        # other modules still off
        self.assertFalse(gate.enabled('causal_memory'))
        os.unlink(f.name)

    def test_set_flag_in_memory(self):
        gate = FeatureGate(config_path='/tmp/__nonexistent__.yaml')
        gate.set_flag('enabled', True)
        gate.set_flag('critic_engine', True)
        self.assertTrue(gate.enabled('critic_engine'))


class TestSpoilTest(unittest.TestCase):
    """
    Non-destructive spoil test:
    Ensure adapter code cannot execute with feature flag OFF.
    """

    def test_adapter_generation_blocked(self):
        gate = FeatureGate(config_path='/tmp/__nonexistent__.yaml')
        self.assertFalse(gate.enabled('adapter_generation'))
        self.assertFalse(gate.enabled('adapter_generator'))

    def test_learning_system_facade_returns_none(self):
        from AgentCore.learning_system import LearningSystem
        ls = LearningSystem()
        # With all flags off, every accessor must return None
        self.assertIsNone(ls.discovery)
        self.assertIsNone(ls.generator)
        self.assertIsNone(ls.critic)
        self.assertIsNone(ls.memory)
        self.assertIsNone(ls.intent)


if __name__ == '__main__':
    unittest.main()
