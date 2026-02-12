"""
Level-4 End-to-End Tests.
"""
import unittest
import os
import shutil
from AgentCore.advanced.level4.engine.orchestrator import Level4Orchestrator
from AgentCore.feature_gate import _policy_manager # Hack to mock feature flag or assume default

class TestLevel4EndToEnd(unittest.TestCase):
    def setUp(self):
        self.orchestrator = Level4Orchestrator()
        
    def test_disabled_by_default(self):
        result = self.orchestrator.handle_code_request("user1", "create foo")
        # Should be disabled
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], "Level-4 Engine disabled")

    # To test enabled path, we'd need to mock is_enabled or change config.
    # Level-4 implementation keeps flags in yaml, loaded by policy manager.
    # We can mock the config loading in tests.

if __name__ == "__main__":
    unittest.main()
