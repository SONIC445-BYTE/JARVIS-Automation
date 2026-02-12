"""
Test Level-6 Orchestrator.
"""
import unittest
from AgentCore.advanced.level6.architect.architect_orchestrator import ArchitectOrchestrator

class TestArchitectOrchestrator(unittest.TestCase):
    def test_proposal_flow(self):
        orch = ArchitectOrchestrator()
        pid = orch.propose_architecture_change("user1", "Migrate to Microservices", {})
        self.assertTrue(pid)
        
        report = orch.evaluate_proposal(pid)
        self.assertEqual(report['status'], 'proposed')
        self.assertTrue(len(report['reports']) > 0)

if __name__ == "__main__":
    unittest.main()
