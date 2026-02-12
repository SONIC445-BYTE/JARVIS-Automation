from typing import Dict, Any, List
import re

class Verifier:
    def verify_plan(self, plan: List[Dict]) -> Dict[str, Any]:
        """
        Static analysis of the plan.
        """
        risks = []
        for step in plan:
            # Check for secrets
            content = step.get("content", "") + str(step.get("spec", ""))
            if re.search(r"(password|secret|key)\s*=", content, re.IGNORECASE):
                risks.append(f"Potential secret in step {step.get('target', '?')}")
                
            # Check for destructive
            if step["type"] == "delete_file":
                risks.append(f"Destructive action: delete {step.get('target')}")

        return {
            "safe": len(risks) == 0,
            "risks": risks
        }
