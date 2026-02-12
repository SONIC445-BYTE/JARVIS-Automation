
import sys
import os

# Ensure AgentCore is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

try:
    from AgentCore.ui_inspector import UIInspector
    inspector = UIInspector()
    print("UIInspector initialized")
    
    if hasattr(inspector, "get_current_state"):
        print("PASS: get_current_state method exists")
        state = inspector.get_current_state()
        print(f"PASS: get_current_state returned: {list(state.keys())}")
    else:
        print("FAIL: get_current_state method MISSING")
        sys.exit(1)
        
except Exception as e:
    print(f"FAIL: Error: {e}")
    sys.exit(1)
