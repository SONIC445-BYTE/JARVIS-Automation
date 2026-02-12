import sys
import os
sys.path.append(os.getcwd())

from AgentCore.ui_agent.adapter_registry import registry
from AgentCore.ui_agent.action_router import ActionPlanner

def test_all_adapters_registered():
    print("Testing Adapter Registration...")
    # Currently we have WhatsApp and Explorer
    count = len(registry.adapters)
    print(f"Registered actions: {list(registry.adapters.keys())}")
    assert count >= 2
    print("Registration test passed")

def test_plan_generation():
    print("Testing Plan Generation...")
    # Test intent as a dictionary
    intent = {"action": "send_message", "platform": "whatsapp", "recipient": "John", "message": "Hi"}
    plan = ActionPlanner.plan(intent, {})
    assert len(plan) > 0
    print(f"Generated WhatsApp plan: {plan}")
    
    intent_exp = {"action": "navigate_to", "platform": "explorer", "path": "C:\\"}
    plan_exp = ActionPlanner.plan(intent_exp, {})
    assert len(plan_exp) > 0
    print(f"Generated Explorer plan: {plan_exp}")
    print("Plan generation test passed")

if __name__ == "__main__":
    try:
        # Need to import UIAgentMain to trigger registrations
        from AgentCore.ui_agent.ui_agent_main import UIAgentMain
        _ = UIAgentMain()
        
        test_all_adapters_registered()
        test_plan_generation()
        print("\nALL ARCHITECTURAL TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
