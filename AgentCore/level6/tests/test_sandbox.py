import unittest
import shutil
import os
from pathlib import Path
from AgentCore.level6.sandbox_runner import SandboxRunner

class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.sandbox_path = "projects/test_sandbox"
        self.runner = SandboxRunner(self.sandbox_path)

    def tearDown(self):
        if os.path.exists(self.sandbox_path):
            shutil.rmtree(self.sandbox_path)

    def test_run_plan(self):
        plan = [{"type": "create_file", "target": "test_script.py", "content": "print('hello')"}]
        tests = []
        result = self.runner.run_plan(plan, tests, "snap_1")
        self.assertTrue(result["passed"])
        self.assertTrue((Path(self.sandbox_path) / str(Path(result["sandbox_dir"]).name) / "test_script.py").exists())

if __name__ == "__main__":
    unittest.main()
