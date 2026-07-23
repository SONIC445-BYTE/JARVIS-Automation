"""
LLM Adapter for Tier-2.
Wraps the local LLM engine and handles prompt management and JSON parsing.
"""
import os
import json
import re
from typing import Dict, Any, List, Optional
from AgentCore.llm_engine import LLMEngine

class LLMAdapter:
    def __init__(self):
        self.engine = LLMEngine()
        self.prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")

    def _load_prompt(self, name: str) -> str:
        try:
            with open(os.path.join(self.prompt_dir, name), 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from LLM response."""
        try:
            # Try direct parse
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON block
            match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass
            # Try without backticks
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass
            return {}

    def plan_refactor(self, goal: str, context: str) -> Dict[str, Any]:
        """Generate a refactor plan."""
        system_prompt = self._load_prompt("refactor_planner.system")
        user_prompt = f"Goal: {goal}\n\nContext:\n{context}"
        
        response = self.engine.chat([
            {"role": "user", "content": user_prompt}
        ], system=system_prompt)
        
        return self._parse_json(response.text)

    def generate_raw(self, prompt: str) -> str:
        """
        Generic passthrough for callers that need to supply a
        fully-formed prompt of their own, rather than one of this
        adapter's fixed templates. suggest_code/plan_refactor/
        verify_safety each embed a specific prompt shape for their own
        purpose (suggest_code's template, for example, has no concept of
        the multi-file "### filename" output convention GeneratorHelper's
        caller (CodeEngine) parses for) -- none of them accept an
        arbitrary prompt. Mirrors exactly what suggest_code() does
        internally, minus the fixed template.
        """
        response = self.engine.generate(prompt)
        return response.text

    def suggest_code(self, goal: str, context_files: str) -> str:
        """Suggest code changes."""
        template = self._load_prompt("code_synth.user")
        prompt = template.format(goal_description=goal, file_summaries=context_files)
        
        response = self.engine.generate(prompt)
        return response.text

    def verify_safety(self, patch: str) -> Dict[str, Any]:
        """Verify patch safety."""
        system_prompt = self._load_prompt("safety.verify")
        user_prompt = f"Patch:\n{patch}"
        
        response = self.engine.chat([
            {"role": "user", "content": user_prompt}
        ], system=system_prompt)
        
        text = response.text.lower()
        if "forbidden" in text:
            return {"verdict": "forbidden", "details": response.text}
        elif "risky" in text:
            return {"verdict": "risky", "details": response.text}
        else:
            return {"verdict": "safe", "details": response.text}
