
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Adjust path to include project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from AgentCore.agent_brain import AgentBrain
from AgentCore.intent_parser import IntentParser
from AgentCore.validation_engine import ValidationEngine, RecoveryAction

class TestAgentHardening(unittest.TestCase):
    
    def setUp(self):
        self.brain = AgentBrain(use_llm_parser=True)
        # Mock LLM to simulate failures
        self.brain.llm_parser = MagicMock()
        
    def test_llm_empty_response_fallback(self):
        """Test that empty LLM response triggers immediate failure/fallback, NOT unknown step."""
        print("\n--- Test: LLM Empty Response ---")
        # LLM returns empty list (simulating "I don't understand")
        self.brain.llm_parser.parse.return_value = []
        
        # Original intent parser fallback (mocked to valid for this test)
        self.brain.parser.parse = MagicMock(return_value=MagicMock(to_dict=lambda: {"action": "search", "target": "python"}))
        
        # Execute
        try:
            # We expect _parse_command to raise ValueError if we don't mock the inner handling
            # But AgentBrain catches it and logs warning.
            # Let's inspect what _parse_command returns.
            result_intent = self.brain._parse_command("search for python")
            
            # Should have fallen back to rule-based parser (Action: search)
            # NOT "llm_sequence" with empty actions.
            self.assertNotEqual(result_intent.get("action"), "llm_sequence")
            print("✓ Fallback successful (Result not llm_sequence)")
            
        except Exception as e:
            self.fail(f"AgentBrain crashed on empty LLM response: {e}")

    def test_fail_fast_unknown_action(self):
        """Test that AgentBrain aborts if plan contains unknown action."""
        print("\n--- Test: Fail Fast Unknown Action ---")
        # Mock intent data to produce unknown action plan
        unknown_intent = {
            "intent_id": "test_id",
            "action": "unknown",
            "raw_command": "do something weird"
        }
        
        # Mock _parse_command to return this
        self.brain._parse_command = MagicMock(return_value=unknown_intent)
        
        # Execute
        result = self.brain.execute_command("do something weird")
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("Plan contains unknown action", result["message"])
        print("✓ Agent aborted on unknown action")

    def test_validation_fatal_error(self):
        """Test that ValidationEngine returns FATAL for unknown/semantic errors."""
        print("\n--- Test: Validation Fatal Error ---")
        validator = ValidationEngine()
        
        # 1. Unknown Action Error
        res = validator._handle_failure("step1", "condition", "failed", "Unknown action type: fly")
        self.assertEqual(res.recovery_action, RecoveryAction.FATAL)
        print("✓ FATAL on 'Unknown action type'")
        
        # 2. Semantic Failure
        res = validator._handle_failure("step1", "condition", "semantic_failure", "Title mismatch")
        self.assertEqual(res.recovery_action, RecoveryAction.FATAL)
        print("✓ FATAL on 'semantic_failure'")
        
        # 3. Normal Failure (Retry)
        res = validator._handle_failure("step1", "condition", "not_found", "Element not found")
        self.assertEqual(res.recovery_action, RecoveryAction.RETRY)
        print("✓ RETRY on normal failure")

if __name__ == "__main__":
    unittest.main()
