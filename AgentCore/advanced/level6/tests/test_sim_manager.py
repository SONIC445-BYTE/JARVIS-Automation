"""
Test Simulation Manager.
"""
import unittest
from AgentCore.advanced.level6.architect.sim_manager import SimManager

class TestSimManager(unittest.TestCase):
    def test_sim_run(self):
        sim = SimManager()
        res = sim.run_simulation({})
        self.assertTrue(res['success'])
        self.assertIn('latency_p99', res['metrics'])

if __name__ == "__main__":
    unittest.main()
