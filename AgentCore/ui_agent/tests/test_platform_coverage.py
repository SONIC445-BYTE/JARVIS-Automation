import sys
import os
import json
import yaml
sys.path.append(os.getcwd())

from AgentCore.ui_agent.ui_agent_main import UIAgentMain
from AgentCore.ui_agent.adapter_registry import registry

def setup_test_env():
    os.makedirs("feature_flags", exist_ok=True)
    with open("feature_flags/ui_vision.yaml", "w") as f:
        yaml.dump({"enabled": True}, f)
    with open("feature_flags/ui_execute.yaml", "w") as f:
        yaml.dump({"enabled": True, "allowlist": ["whatsapp", "explorer", "notepad", "acorns", "unknown_app"]}, f)

def test_full_platform_coverage():
    print("\n--- Testing Full Platform Coverage ---")
    setup_test_env()
    
    # Initialize agent (triggers DynamicAdapterLoader)
    # Using a fresh registry to ensure we count correctly
    registry.adapters = {} 
    agent = UIAgentMain()
    
    # 1. Assert Folder Enforcement
    platform_dir = "AgentCore/platform_adapters"
    folders = [f.name for f in os.scandir(platform_dir) if f.is_dir()]
    print(f"Total folders found: {len(folders)}")
    
    # Check uniquely registered platforms
    registered_platforms = set()
    for adapter_list in registry.adapters.values():
        for a in adapter_list:
            plat = getattr(a, 'platform', '').lower()
            if plat:
                registered_platforms.add(plat)
            
    print(f"Total platforms registered: {len(registered_platforms)}")
    
    # Every folder must have at least one adapter
    for folder in folders:
        assert folder in registered_platforms, f"Folder '{folder}' was not registered!"

    # 2. Hard Planning Invariant Test
    print("\nVerifying Hard Planning Invariant...")
    test_cases = [
        {"action": "send_message", "platform": "whatsapp"},
        {"action": "click", "platform": "acorns"},
        {"action": "unknown_action", "platform": "notepad"},
        {"action": "do_something", "platform": "unknown_app"}
    ]
    
    for case in test_cases:
        print(f"  Testing: {case}")
        adapter, plan = agent.planner.plan(case, {})
        assert adapter is not None
        assert len(plan) > 0, f"Plan for {case} was empty!"
        print(f"    [OK] Selected: {os.path.basename(str(adapter.__class__))}")

    # 3. Execution & Escalation Test (Dry Run)
    print("\nVerifying UI Escalation Ladder (Traceability)...")
    instruction = "Click Login in unknown_app"
    # Mocking infer_action for the test
    agent._infer_action = lambda x: {"action": "click", "platform": "unknown_app", "target": "Login"}
    
    # Set exec_all to 0 for dry run, but ActionExecutor already defaults to True for dry_run
    result = agent.execute_instruction(instruction, dry_run=False) # ActionExecutor defaults dry_run=True inside
    
    # Check traceability metadata
    for step in result.steps:
        print(f"  Step Trace: {step}")
        assert "platform" in step
        assert "adapter" in step
        assert "fallback" in step
        assert step["fallback"] in ["native", "ui", "unknown"]

    print("\n--- All Coverage Tests Passed ---")

if __name__ == "__main__":
    try:
        test_full_platform_coverage()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
