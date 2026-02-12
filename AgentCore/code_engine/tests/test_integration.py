"""
Test Integration.
"""
import unittest
import os
import shutil
from AgentCore.code_engine.engine import CodeEngine

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = CodeEngine()
        # Mock policy to enabled
        self.engine.policy.config["enabled"] = True
        
    def test_routing(self):
        # Since we mocked Tier-1 handling as error in engine.py for now, check that.
        result = self.engine.handle_command("create file using template X")
        # Should route to Tier-1
        # self.assertEqual(result['message'], "Tier-1 parsing not implemented yet")
        pass

    def test_tier2_flow(self):
        # Mock check
        pass

if __name__ == "__main__":
    unittest.main()
