"""
Test Guards.
"""
import unittest
from AgentCore.guards.resource_guard import ResourceGuard
from AgentCore.workspace.namespace_manager import NamespaceManager
from AgentCore.monitoring.anomaly_rules import AnomalyRules

class TestGuards(unittest.TestCase):
    def test_resource_guard(self):
        guard = ResourceGuard()
        # Should allow first request
        self.assertTrue(guard.allow_request("tier2"))
        # Should block immediate second request (cooldown)
        self.assertFalse(guard.allow_request("tier2"))
        
    def test_namespace(self):
        ns = NamespaceManager()
        self.assertTrue(ns.register_experiment("default", "exp1"))

    def test_anomaly_rules(self):
        rules = AnomalyRules()
        self.assertEqual(rules.get_action("security_violation"), "escalate")

if __name__ == "__main__":
    unittest.main()
