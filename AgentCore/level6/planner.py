import json
from typing import Dict, Any, List, Optional

class Planner:
    def __init__(self, llm_adapter):
        self.llm = llm_adapter

    def plan_refactor(self, goal: str, context_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a refactoring plan and tests.
        """
        prompt = (
            "SYSTEM: You are Level6 Planner. Given a short goal and repository context summary, output JSON:\n"
            "{\n"
            '  "plan": [ { "type": "create_file|ast_edit|update_file", "target": "<path>", "spec": {...} } ],\n'
            '  "tests": [ { "path": "<tests/...>", "content": "..." } ],\n'
            '  "estimated_risk": 0.0-1.0,\n'
            '  "explain": "one-paragraph rationale"\n'
            "}\n"
            "Do not execute anything. Minimal code in tests; keep functions small.\n\n"
            f"Goal: {goal}\n"
            f"Context: {json.dumps(context_summary, default=str)[:1000]}" # Limit context size
        )

        try:
            if not self.llm:
                # Mock for testing if no LLM
                return self._mock_plan(goal)
                
            response = self.llm.generate(prompt)
            return self._parse_json(response)
        except Exception as e:
            print(f"[Planner] Error: {e}")
            return {"error": str(e), "plan": [], "tests": []}

    def _parse_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"): 
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Simple retry or fallback
            return {"error": "Invalid JSON from LLM", "raw": text}

    def _mock_plan(self, goal: str) -> Dict[str, Any]:
        return {
            "plan": [],
            "tests": [],
            "estimated_risk": 0.0,
            "explain": "Mock plan (No LLM)"
        }
