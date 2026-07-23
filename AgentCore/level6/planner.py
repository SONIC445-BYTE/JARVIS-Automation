import json
import re
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
            '  "plan": [ { "type": "create_file|ast_edit|update_file", "target": "<path>", "content": "...", "spec": {...} } ],\n'
            '  "tests": [ { "path": "<tests/...>", "content": "..." } ],\n'
            '  "estimated_risk": 0.0-1.0,\n'
            '  "explain": "one-paragraph rationale"\n'
            "}\n"
            'For type "create_file"/"update_file", put the full file content in "content". '
            'For type "ast_edit" (editing one function in an existing file without rewriting the whole file), '
            'spec must be {"type": "replace_function", "name": "<function name>", "code": "<full corrected def ...>"}.\n'
            "Do not execute anything. Minimal code in tests; keep functions small.\n\n"
            f"Goal: {goal}\n"
            f"Context: {json.dumps(context_summary, default=str)[:1000]}" # Limit context size
        )

        try:
            if not self.llm:
                # Mock for testing if no LLM
                return self._mock_plan(goal)
                
            # Same interface-mismatch bug class as GeneratorHelper's
            # original bug (AgentCore/code_engine/generator_helper.py):
            # generate() was never a real method on LLMAdapter.
            # generate_raw() is the real, verified passthrough, and
            # already returns a plain string (.text), matching
            # _parse_json()'s str parameter.
            response = self.llm.generate_raw(prompt)
            return self._parse_json(response)
        except Exception as e:
            print(f"[Planner] Error: {e}")
            return {"error": str(e), "plan": [], "tests": []}

    # Found live during Phase C verification: the LLM sometimes embeds
    # Python-style triple-quoted strings as JSON string values (e.g.
    # "code": """\ndef foo():\n    pass\n"""), which isn't valid JSON --
    # only "..." with \n-style escapes is. Converts each """...""" block
    # into a properly JSON-escaped double-quoted string before parsing,
    # rather than failing outright on otherwise-correct, well-structured
    # output.
    _TRIPLE_QUOTE_RE = re.compile(r'"""(.*?)"""', re.DOTALL)

    @classmethod
    def _normalize_triple_quoted_strings(cls, text: str) -> str:
        return cls._TRIPLE_QUOTE_RE.sub(lambda m: json.dumps(m.group(1)), text)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """
        Found live during Phase A verification: real LLM responses
        routinely include prose before the JSON (e.g. "Here is the JSON
        output:\n\n```\n{...}\n```"), which the old startswith("```")-only
        check missed entirely -- the fence has to be the very first
        character for that check to fire at all. Same "edge-only" shape
        as GeneratorHelper's original fence-stripping bug. Mirrors the
        already-working, more robust extraction chain LLMAdapter._parse_json
        uses elsewhere in this codebase: direct parse, then a fenced
        block found anywhere in the text, then the widest {...} span as
        a last resort.
        """
        cleaned = self._normalize_triple_quoted_strings(text.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return {"error": "Invalid JSON from LLM", "raw": text}

    def _mock_plan(self, goal: str) -> Dict[str, Any]:
        return {
            "plan": [],
            "tests": [],
            "estimated_risk": 0.0,
            "explain": "Mock plan (No LLM)"
        }
