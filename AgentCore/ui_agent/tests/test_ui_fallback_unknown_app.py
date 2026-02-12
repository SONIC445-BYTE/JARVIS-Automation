import sys
import os
import yaml
import json
sys.path.append(os.getcwd())

from AgentCore.ui_agent.ui_agent_main import UIAgentMain

def setup_flags():
    os.makedirs("feature_flags", exist_ok=True)
    with open("feature_flags/ui_vision.yaml", "w") as f:
        yaml.dump({"enabled": True}, f)
    with open("feature_flags/ui_execute.yaml", "w") as f:
        yaml.dump({
            "enabled": True,
            "allowlist": ["whatsapp", "explorer", "notepad"]
        }, f)

def test_unknown_app_fallback():
    print("\n--- Testing Unknown App Fallback ---")
    setup_flags()
    
    agent = UIAgentMain()
    
    # "Notepad" has no specific adapter
    instruction = "Type hello in Notepad"
    print(f"Instruction: {instruction}")
    
    # Mocking _infer_action to return an unknown app intent
    # In real use, LLM would do this
    agent._infer_action = lambda x: {"action": "type", "platform": "notepad", "target": "document", "value": "hello"}
    
    result = agent.execute_instruction(instruction, dry_run=False)
    
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print(f"Steps: {result.steps}")
    
    # Assertions
    assert result.success is True
    # Should have triggered OCR click or generic type via UnknownAppFallbackAdapter
    assert any(s["action"] == "ocr_click" or s["action"] == "type" for s in result.steps)
    
    # Check Audit Logs
    audit_dir = "data/ui_actions/"
    if os.path.exists(audit_dir):
        logs = os.listdir(audit_dir)
        print(f"Audit logs found: {logs}")
        assert len(logs) > 0
    else:
        print("WARNING: Audit directory not found!")

    print("--- Fallback Test Passed ---")

if __name__ == "__main__":
    try:
        test_unknown_app_fallback()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
