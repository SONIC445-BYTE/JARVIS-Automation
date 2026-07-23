import unittest
import shutil
import os
from AgentCore.level6.orchestrator import Level6Coordinator
from AgentCore.level6.planner import Planner

class TestLevel6Core(unittest.TestCase):
    def setUp(self):
        self.config_path = "feature_flags/test_level6.yaml"
        with open(self.config_path, "w") as f:
            f.write("enabled: true\n")

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_orchestrator_planning(self):
        coord = Level6Coordinator(self.config_path)
        # No llm= passed -> Planner falls back to _mock_plan() (empty
        # plan/tests). Phase A wires the plan through SandboxRunner
        # (trivially "passed" with no tests to run) and Verifier
        # (trivially "safe" with an empty plan), so the pipeline now
        # completes as "verified" rather than stopping at the old
        # "planned"-only proof-of-concept status.
        result = coord.handle_request("Refactor user model", {})
        self.assertEqual(result["status"], "verified")
        self.assertIn("plan", result)
        self.assertIn("sandbox_result", result)
        self.assertIn("verify_result", result)

    def test_planner_mock(self):
        planner = Planner(None)
        res = planner.plan_refactor("test goal", {})
        self.assertIn("plan", res)
        self.assertEqual(res["estimated_risk"], 0.0)

if __name__ == "__main__":
    unittest.main()
