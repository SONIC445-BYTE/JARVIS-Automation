import unittest

from AgentCore.level6.debug_loop import DebugLoop


class MockFixer:
    def apply_transform(self, content, spec):
        return content


class FixApplyingRunner:
    """Passes only once the plan's file content actually contains the fix."""

    def run_plan(self, plan, tests, snap):
        fixed = any(
            "return a + b" in step.get("content", "")
            for step in plan
        )
        if fixed:
            return {"passed": True, "stdout": "1 passed", "stderr": ""}
        return {"passed": False, "stdout": "NameError: name 'add' is not defined", "stderr": ""}


class RealFixLLM:
    def generate_raw(self, prompt):
        return "### add.py\ndef add(a, b):\n    return a + b\n"


class AlwaysFailRunner:
    def run_plan(self, plan, tests, snap):
        return {"passed": False, "stdout": "still fails", "stderr": ""}


class UnparsableLLM:
    def generate_raw(self, prompt):
        return "I'm not sure how to fix this, sorry."


class SameFixEveryTimeLLM:
    def generate_raw(self, prompt):
        return "### x.py\nstill broken content\n"


class TestDebugLoop(unittest.TestCase):
    def test_iterate_applies_a_real_fix_and_succeeds_on_retry(self):
        """
        Regression test for the old no-op-retry behavior (Phase B
        replaced it): this now asserts the fix content actually reached
        the plan and that success is a genuine consequence of the fix,
        not a coincidental mock-call count.
        """
        plan = [{"type": "create_file", "target": "add.py", "content": "def add(a, b):\n    pass"}]
        loop = DebugLoop(RealFixLLM(), FixApplyingRunner(), MockFixer())

        res = loop.iterate(plan, [], "snap")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["iterations"], 2)
        self.assertIn("return a + b", res["final_plan"][0]["content"])

    def test_iterate_stops_early_when_fix_response_does_not_parse(self):
        """
        A fix iteration that changes nothing (unparsable response, or a
        response naming a file that isn't part of the plan) must stop
        immediately rather than burn the rest of the iteration budget
        retrying an identical, still-failing plan.
        """
        plan = [{"type": "create_file", "target": "x.py", "content": "bad"}]
        loop = DebugLoop(UnparsableLLM(), AlwaysFailRunner(), MockFixer())

        res = loop.iterate(plan, [], "snap")

        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["reason"], "No usable fix produced")
        self.assertEqual(res["iterations"], 1)

    def test_iterate_exhausts_budget_when_fix_never_actually_fixes_it(self):
        plan = [{"type": "create_file", "target": "x.py", "content": "bad"}]
        loop = DebugLoop(SameFixEveryTimeLLM(), AlwaysFailRunner(), MockFixer())

        res = loop.iterate(plan, [], "snap")

        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["reason"], "Budget exhausted")
        self.assertEqual(res["iterations"], 5)
        # Consistency with the other two return paths -- orchestrator.py
        # reads this into sandbox_result regardless of which failure
        # path triggered.
        self.assertIn("evidence", res)
        self.assertEqual(res["evidence"]["stdout"], "still fails")

    def test_iterate_never_modifies_tests(self):
        """Tests are the specification/oracle -- a fix must never rewrite them."""
        plan = [{"type": "create_file", "target": "add.py", "content": "bad"}]
        tests = [{"path": "test_add.py", "content": "def test_add():\n    assert add(2, 3) == 5\n"}]

        class FixTargetingTestFile:
            def generate_raw(self, prompt):
                return "### test_add.py\ndef test_add():\n    assert True\n"

        loop = DebugLoop(FixTargetingTestFile(), AlwaysFailRunner(), MockFixer())
        res = loop.iterate(plan, tests, "snap")

        # The fix named only the test file, which is never eligible to
        # be changed -- so nothing in the plan changes, and the loop
        # stops honestly instead of looping on an unchanged plan.
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["reason"], "No usable fix produced")


if __name__ == "__main__":
    unittest.main()
