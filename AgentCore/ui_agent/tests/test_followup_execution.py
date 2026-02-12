import unittest
from unittest.mock import MagicMock, patch
from AgentCore.ui_agent.context.ui_context import UIContext
from AgentCore.ui_agent.planner.followup_guard import FollowupGuard

class TestFollowupExecution(unittest.TestCase):
    
    def setUp(self):
        # Reset singleton
        UIContext._instance = None
        self.ctx = UIContext()
        
    def test_session_persistence(self):
        """Test that session ID persists."""
        sid1 = self.ctx.get_session_id()
        self.ctx.set_active(True, "test_adapter")
        
        # Simulate re-access
        ctxvh = UIContext()
        self.assertEqual(ctxvh.get_session_id(), sid1)
        self.assertTrue(ctxvh.is_active())
        
    def test_followup_detection(self):
        """Test detection of follow-up intents."""
        intent = MagicMock()
        intent.action = "click"
        
        # Context inactive -> False
        self.assertFalse(FollowupGuard.is_followup(intent, self.ctx))
        
        # Context active -> True
        self.ctx.set_active(True, "adapter_A")
        self.assertTrue(FollowupGuard.is_followup(intent, self.ctx))
        
    def test_adapter_ownership(self):
        """Test adapter ownership validation."""
        self.ctx.set_active(True, "adapter_A")
        
        # Same adapter -> OK
        self.assertTrue(self.ctx.validate_ownership("adapter_A"))
        
        # Different adapter -> Fail
        # In current impl it prints warning but returns False? 
        # Let's check implementation behavior
        self.assertFalse(self.ctx.validate_ownership("adapter_B"))

if __name__ == '__main__':
    unittest.main()
