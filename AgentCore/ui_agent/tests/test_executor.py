import sys
import os
sys.path.append(os.getcwd())
from AgentCore.ui_agent.executor.ui_executor import UIExecutor
from AgentCore.ui_agent.inspector.accessibility_adapter import AccessibilityAdapter
from AgentCore.ui_agent.inspector.browser_adapter import BrowserAdapter

def test_executor_dry_run():
    print("Testing Executor Dry-Run...")
    acc = AccessibilityAdapter()
    browser = BrowserAdapter()
    executor = UIExecutor(acc, browser)
    
    plan = [
        {"type": "click", "target": "button[text='Test']"},
        {"type": "type", "target": "input", "value": "hello"}
    ]
    
    result = executor.execute(plan, dry_run=True)
    assert result.success == True
    assert len(result.steps) == 2
    print("Dry-run execution passed")

if __name__ == "__main__":
    test_executor_dry_run()
