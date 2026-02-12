"""
Explainers for Tier-2.
Generates human-readable explanations for code.
"""
from typing import Dict, Any
from .llm_adapter import LLMAdapter

class CodeExplainer:
    def __init__(self):
        self.adapter = LLMAdapter()

    def explain_code(self, code: str, context: str = "") -> str:
        """Explain a piece of code."""
        prompt = f"Explain the following code clearly:\n\n{code}\n\nContext: {context}"
        response = self.adapter.engine.generate(prompt)
        return response.text
