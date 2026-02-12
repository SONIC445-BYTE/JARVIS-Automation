import sys
import os
sys.path.append(os.getcwd())

from AgentCore.ui_agent.ui_agent_main import UIAgentMain

def test_ui_agent_smoke():
    print("Testing UI Agent Smoke Test (Dry-run)...")
    agent = UIAgentMain()
    
    # Enable visibility for test
    agent.vision_enabled = True
    
    instructions = [
        "Send message on WhatsApp to JARVIS",
        "Navigate explorer to C: drive"
    ]
    
    for instr in instructions:
        print(f"Processing: {instr}")
        result = agent.execute_instruction(instr, dry_run=True)
        print(f"Result Success: {result.success}")
        print(f"Steps Planned: {len(result.steps)}")
        for i, step in enumerate(result.steps):
            print(f"  Step {i+1}: {step}")
        print("-" * 20)
        
    if all(len(agent.execute_instruction(i, True).steps) > 0 for i in instructions):
        print("SMOKE TEST PASSED")
        return True
    return False

if __name__ == "__main__":
    test_ui_agent_smoke()
