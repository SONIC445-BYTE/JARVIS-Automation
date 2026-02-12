import os
import sys
from ..adapter_registry import registry
from typing import Any

class SystemHealthGuard:
    """Startup validation for the UI Agent system."""
    
    def __init__(self, agent: Any):
        self.agent = agent
        self.verdict = "UNKNOWN"

    def run_checks(self):
        print("[HealthGuard] Starting UI System Integrity Checks...")
        errors = []
        
        # 1. Registry Check
        if not registry.adapters:
            errors.append("AdapterRegistry is empty. No platform adapters loaded.")
            
        # 2. Planning Check
        try:
            # Test a basic navigation plan
            plan = self.agent.planner.plan({"action": "navigate_to", "platform": "explorer", "path": "C:\\"}, {})
            if not plan:
                errors.append("ActionPlanner returned empty plan for known action.")
        except Exception as e:
            errors.append(f"ActionPlanner check failed: {e}")
            
        # 3. Connection Check (Accessibility API)
        try:
            windows = self.agent.acc_adapter.list_windows()
            if not windows:
                errors.append("UI Inspector (Accessibility API) unreachable or returned no windows.")
        except Exception as e:
            errors.append(f"UI Inspector check failed: {e}")
            
        if errors:
            self.verdict = "FAIL"
            print(f"[HealthGuard] CRITICAL FAILURES DETECTED:")
            for err in errors:
                print(f"  - {err}")
            # In a real system, might fail fast or disable features
        else:
            self.verdict = "PASS"
            print("[HealthGuard] UI System is healthy.")
            
        self._log_verdict(errors)
        return self.verdict == "PASS"

    def _log_verdict(self, errors):
        log_path = os.path.join("data", "logs", "ui_health.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"[{self.verdict}] Errors: {errors}\n")

def check_system_health(agent):
    guard = SystemHealthGuard(agent)
    return guard.run_checks()
