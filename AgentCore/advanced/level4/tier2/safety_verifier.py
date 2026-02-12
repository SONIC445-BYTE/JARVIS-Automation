"""
Safety Verifier for Level-4.
"""
from typing import Dict, Any, List

class SafetyVerifier:
    def verify_plan(self, plan: Dict[str, Any]) -> str:
        # Check for forbidden ops
        # Mock implementation
        risks = []
        for step in plan.get("steps", []):
            if step['type'] == 'delete_file':
                return "forbidden"
            if step['type'] == 'network_call':
                return "risky"
        return "safe"
