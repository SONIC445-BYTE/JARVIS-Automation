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

    def test_run_plan_with_a_real_passing_test(self):
        """
        Regression test for a bug found live (Phase A verification):
        run_plan() joined sandbox_dir onto each test path AND ran the
        pytest subprocess with cwd=sandbox_dir -- double-prepending the
        sandbox path, so pytest could never find the tests it had just
        written. The prior test (tests=[]) never exercised this, since
        an empty list takes the early "No tests to run" return instead.
        This uses a genuinely passing test to confirm pytest actually
        finds and runs it, not just that run_plan() doesn't crash.
        """
        plan = [{"type": "create_file", "target": "add.py", "content": "def add(a, b):\n    return a + b\n"}]
        tests = [{
            "path": "test_add.py",
            "content": "from add import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        }]
        result = self.runner.run_plan(plan, tests, "snap_2")
        self.assertTrue(result["passed"], result.get("stdout", "") + result.get("stderr", ""))
        self.assertIn("1 passed", result["stdout"])

    def test_run_plan_with_a_real_failing_test(self):
        plan = [{"type": "create_file", "target": "add.py", "content": "def add(a, b):\n    return a - b\n"}]
        tests = [{
            "path": "test_add.py",
            "content": "from add import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        }]
        result = self.runner.run_plan(plan, tests, "snap_3")
        self.assertFalse(result["passed"])
        self.assertIn("1 failed", result["stdout"])

    def test_run_plan_treats_passing_bare_assert_test_as_passed(self):
        """
        Regression test for a false negative found live (Phase B
        verification): the Planner's LLM sometimes writes tests as bare
        top-level `assert` statements rather than `def test_...()`
        functions. Such a file is genuinely exercised at import time --
        pytest just doesn't recognize it as a collectible "test item",
        and returns exit code 5 ("no tests ran") when the assert passes
        cleanly. The old `returncode == 0` check treated that as a
        failure, discarding a fix that had actually worked.
        """
        plan = [{"type": "create_file", "target": "add.py", "content": "def add(a, b):\n    return a + b\n"}]
        tests = [{
            "path": "test_add.py",
            "content": "import add\nassert add.add(2, 3) == 5\n",
        }]
        result = self.runner.run_plan(plan, tests, "snap_4")
        self.assertTrue(result["passed"], result.get("stdout", "") + result.get("stderr", ""))

    def test_run_plan_treats_failing_bare_assert_test_as_failed(self):
        plan = [{"type": "create_file", "target": "add.py", "content": "def add(a, b):\n    return a - b\n"}]
        tests = [{
            "path": "test_add.py",
            "content": "import add\nassert add.add(2, 3) == 5\n",
        }]
        result = self.runner.run_plan(plan, tests, "snap_5")
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
