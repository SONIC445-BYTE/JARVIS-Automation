"""
Planner for Level-4.
Uses LLM to create plans.
"""
from typing import Dict, Any
from .safety_verifier import SafetyVerifier
from .llm_adapter import LLMAdapter

class Planner:
    def __init__(self):
        self.verifier = SafetyVerifier()
        self.llm = LLMAdapter()

    def create_plan(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Generate plan using LLM
        plan = self.llm.generate_plan(goal)
        
        
        # Verify safety
        safety = self.verifier.verify_plan(plan)
        
        if safety == "forbidden":
            raise ValueError("Plan rejected by safety verifier: Forbidden operations detected.")

        # Gap 5 - Self-Awareness / Confidence Check
        confidence = plan.get('confidence', 0.0)
        CONFIDENCE_THRESHOLD = 0.8
        if confidence < CONFIDENCE_THRESHOLD:
             # Level-5 Awareness: know limits
             return {
                 "status": "aborted",
                 "reason": "low_confidence",
                 "confidence": confidence,
                 "message": "I am not confident enough to proceed with this plan safely."
             }
            
        plan['safety_verdict'] = safety
        return plan
