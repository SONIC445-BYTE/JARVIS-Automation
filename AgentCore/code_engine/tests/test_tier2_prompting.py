"""
Test Tier-2 Prompting.
"""
import unittest
from AgentCore.code_engine.tier2.llm_adapter import LLMAdapter

class TestTier2Prompting(unittest.TestCase):
    def setUp(self):
        self.adapter = LLMAdapter()

    def test_json_parsing(self):
        # Mock LLM response
        fake_response = 'Here is the plan:\n```json\n{"plan": [], "confidence": 0.9}\n```'
        result = self.adapter._parse_json(fake_response)
        self.assertIn("plan", result)
        self.assertEqual(result["confidence"], 0.9)

if __name__ == "__main__":
    unittest.main()
