import unittest
from AgentCore.level6.debug_loop import DebugLoop

class MockRunner:
    def __init__(self):
        self.calls = 0
    def run_plan(self, plan, tests, snap):
        self.calls += 1
        return {"passed": self.calls > 1, "stdout": "fail" if self.calls <= 1 else "pass", "stderr": ""}

class MockLLM:
    def generate(self, prompt): return "{}"

class MockFixer:
    def apply_transform(self, content, spec): return content

class TestDebugLoop(unittest.TestCase):
    def test_iterate_success(self):
        loop = DebugLoop(MockLLM(), MockRunner(), MockFixer())
        res = loop.iterate([], [], "snap")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["iterations"], 2)

if __name__ == "__main__":
    unittest.main()
