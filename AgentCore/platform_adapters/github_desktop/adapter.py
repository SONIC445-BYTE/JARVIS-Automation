from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan

try:
    from ...intent_planner import ExecutionStep
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class ExecutionStep:
        action: str = ""
        target: str = ""
        parameters: dict = None

import subprocess, os


class GithubDesktopAdapter(BaseAdapter):
    """Adapter for GitHub Desktop (local desktop application)."""

    EXE_HINT = "GitHubDesktop.exe"

    @property
    def platform_name(self) -> str:
        return "GitHub Desktop"

    @property
    def supported_actions(self) -> List[str]:
        return ["repository_cloned", "repository_added_from_local", "repository_created", "repository_opened", "branch_created", "branch_switched", "branch_renamed", "branch_deleted", "commit_created", "commit_amended", "commit_undone", "changes_staged", "changes_unstaged", "changes_discarded", "push_executed", "pull_executed", "fetch_executed", "pull_request_created", "merge_branch_executed", "conflict_resolved", "stash_created", "stash_restored", "diff_viewed", "history_viewed", "blame_viewed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "githubdesktop" in title or "githubdesktop" in title or "githubdesktop" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name not in self.supported_actions:
            return Plan(steps=[], confidence=0.0)
        # Default: launch the application if not running
        steps.append(ExecutionStep(
            action="launch_app",
            target=self.EXE_HINT,
            parameters={"exe": self.EXE_HINT, "action": action_name, **params}
        ))
        return Plan(steps=steps, confidence=0.80)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        title = ui_snapshot.get("active_window", "").lower()
        return "githubdesktop" in title
