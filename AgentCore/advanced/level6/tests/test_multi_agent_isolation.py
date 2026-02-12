"""
Test Multi-Agent Isolation.
"""
import unittest
from AgentCore.advanced.level6.multi_agent.coordinator import AgentCoordinator

class TestMultiAgentIsolation(unittest.TestCase):
    def test_agent_spawn(self):
        coord = AgentCoordinator()
        coord.spawn_agent("planner")
        self.assertIn("planner", coord.agents)

if __name__ == "__main__":
    unittest.main()
