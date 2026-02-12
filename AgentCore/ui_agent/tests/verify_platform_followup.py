
import unittest
from unittest.mock import MagicMock, patch
from AgentCore.ui_agent.ui_agent_main import UIAgentMain
from AgentCore.ui_agent.action_router import ActionPlanner

class TestPlatformFollowUp(unittest.TestCase):
    
    def setUp(self):
        self.agent = UIAgentMain()
        # Mock actual execution to prevent side effects during planning check
        self.agent.action_executor.execute = MagicMock(return_value=MagicMock(success=True, steps=[{"ok": True}]))
        self.agent.executor.execute = MagicMock(return_value=MagicMock(success=True, steps=[{"ok": True}]))

    def test_file_explorer_followup(self):
        print("\n=== TEST: Open Explorer -> Click Desktop ===")
        
        # Step 1: Open Explorer
        print("\n[Step 1] User: 'Open File Explorer'")
        intent_1 = self.agent._infer_action("Open File Explorer")
        print(f"Intent 1: {intent_1}")
        
        adapter_1, plan_1 = self.agent.planner.plan(intent_1, {})
        print(f"Plan 1 Adapter: {adapter_1.__class__.__name__}")
        print(f"Plan 1 Steps: {plan_1}")
        
        self.assertEqual(adapter_1.__class__.__name__, "FileExplorerAdapter", "Step 1 should use FileExplorerAdapter")
        
        # Step 2: Click on Desktop (Follow-up)
        print("\n[Step 2] User: 'Click on Desktop'")
        intent_2 = self.agent._infer_action("Click on Desktop")
        # _infer_action currently maps "Click on..." to generic click
        print(f"Intent 2: {intent_2}")
        
        
        # Simulate successful execution of Step 1 setting the context
        self.agent.context["active_app"] = "explorer"
        
        adapter_2, plan_2 = self.agent.planner.plan(intent_2, self.agent.context)
        print(f"Plan 2 Adapter: {adapter_2.__class__.__name__}")
        print(f"Plan 2 Steps: {plan_2}")
        
        # EXPECTATION: 
        # Since FileExplorerAdapter doesn't support 'click', and GenericDesktop is nerfed,
        # checking if it falls back nicely or fails.
        # Ideally, FileExplorerAdapter SHOULD handle this if it's the active context (not implemented yet).
        
        if adapter_2.__class__.__name__ == "UnknownAppFallbackAdapter":
            print("RESULT: Fell back to UnknownApp (OCR) - Expected for current implementation")
        elif adapter_2.__class__.__name__ == "GenericDesktopAdapter":
             print("RESULT: Used GenericDesktop - Check if 'click' is allowed (should be nerfed!)")
        else:
             print(f"RESULT: Handled by {adapter_2.__class__.__name__}")

if __name__ == "__main__":
    unittest.main()
