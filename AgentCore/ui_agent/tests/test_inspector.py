import sys
import os
sys.path.append(os.getcwd())
import pytest
from AgentCore.ui_agent.inspector.accessibility_adapter import AccessibilityAdapter

def test_inspector_basic():
    print("Testing Accessibility Inspector...")
    inspector = AccessibilityAdapter()
    windows = inspector.list_windows()
    assert isinstance(windows, list)
    print(f"Found {len(windows)} windows")
    
if __name__ == "__main__":
    test_inspector_basic()
