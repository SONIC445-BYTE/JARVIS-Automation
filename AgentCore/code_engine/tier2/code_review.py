"""
Code Reviewer for Tier-2.
Uses LLM to review code and plan refactors.
"""
from typing import Dict, Any, List
from .llm_adapter import LLMAdapter

class CodeReviewer:
    def __init__(self):
        self.adapter = LLMAdapter()

    def plan_refactor(self, goal: str, repo_snapshot: Dict[str, str]) -> Dict[str, Any]:
        """
        Plan a refactor based on a goal and repo snapshot.
        repo_snapshot: Dict[filepath, content]
        """
        # Summarize context to fit in token limit
        context_summary = ""
        for path, content in repo_snapshot.items():
            context_summary += f"File: {path}\nContent (first 50 lines):\n"
            context_summary += "\n".join(content.splitlines()[:50])
            context_summary += "\n...\n\n"
            
        return self.adapter.plan_refactor(goal, context_summary)

    def review_patch(self, patch: str) -> Dict[str, Any]:
        """Review a patch for safety and quality."""
        return self.adapter.verify_safety(patch)
