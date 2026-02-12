import json
from typing import List, Dict, Any, Optional

class TestGenerator:
    def __init__(self, llm_adapter):
        self.llm = llm_adapter

    def generate_tests(self, file_path: str, behavior_spec: str) -> List[Dict[str, str]]:
        """
        Generate unit tests for a given file based on behavior spec.
        Returns list of {path: ..., content: ...}
        """
        if not self.llm:
            return self._mock_tests(file_path)

        prompt = (
            f"SYSTEM: You are TestGenerator. For the file {file_path}, generate unit tests covering normal, boundary, and error cases.\n"
            f"Behavior: {behavior_spec}\n"
            "Return JSON list: [ { \"path\": \"tests/test_...\", \"content\": \"...\" } ]\n"
            "Do not include markdown."
        )
        
        try:
            response = self.llm.generate(prompt)
            return self._parse_json(response)
        except Exception as e:
            print(f"[TestGen] Error: {e}")
            return []

    def _parse_json(self, text: str):
        # ... validation logic similar to Planner ...
        try:
            clean = text.strip()
            if clean.startswith("```"): clean = "\n".join(clean.splitlines()[1:-1])
            return json.loads(clean)
        except:
            return []

    def _mock_tests(self, file_path: str) -> List[Dict[str, str]]:
        return [{
            "path": f"tests/test_{file_path.replace('.py','').replace('/','_')}.py",
            "content": "import unittest\nclass TestMock(unittest.TestCase):\n    def test_example(self):\n        self.assertTrue(True)"
        }]
