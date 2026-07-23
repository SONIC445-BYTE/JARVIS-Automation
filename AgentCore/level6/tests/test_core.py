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

    def test_parse_json_handles_triple_quoted_string_values(self):
        """
        Regression test for a real failure found live (Phase C
        verification): the LLM sometimes embeds Python-style
        triple-quoted strings as JSON string values (invalid JSON --
        only "..." with \\n-style escapes is valid). This is the exact
        raw response captured live, which correctly expressed an
        ast_edit plan (proving the Phase C prompt update works) but
        failed to parse for this reason.
        """
        raw = (
            'Here is the plan in JSON format:\n\n```\n{\n'
            '  "plan": [\n    {\n      "type": "ast_edit",\n'
            '      "target": "divide.py",\n      "spec": {\n'
            '        "type": "replace_function",\n'
            '        "name": "divide",\n'
            '        "code": """\ndef divide(a, b):\n    if b == 0:\n'
            '        return None\n    else:\n        return a / b\n"""\n'
            '      }\n    }\n  ],\n'
            '  "estimated_risk": 0.0,\n'
            '  "explain": "Edit the divide function."\n}\n```'
        )
        planner = Planner(None)

        result = planner._parse_json(raw)

        self.assertNotIn("error", result)
        self.assertEqual(result["plan"][0]["type"], "ast_edit")
        self.assertEqual(result["plan"][0]["spec"]["name"], "divide")
        self.assertIn("return None", result["plan"][0]["spec"]["code"])


if __name__ == "__main__":
    unittest.main()
