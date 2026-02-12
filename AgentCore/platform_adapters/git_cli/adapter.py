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


class GitCliAdapter(BaseAdapter):
    """Adapter for Git CLI (local desktop application)."""

    EXE_HINT = "git.exe"

    @property
    def platform_name(self) -> str:
        return "Git CLI"

    @property
    def supported_actions(self) -> List[str]:
        return ["git_init_executed", "git_clone_executed", "git_add_file_executed", "git_add_all_executed", "git_add_interactive_executed", "git_status_executed", "git_diff_executed", "git_diff_cached_staged_executed", "git_commit_executed", "git_commit_amend_executed", "git_log_viewed", "git_blame_viewed", "git_branch_created", "git_branch_deleted", "git_branch_renamed", "git_branch_list_shown", "git_checkout_branch_executed", "git_checkout_new_branch_executed", "git_merge_branch_executed", "git_merge_abort_executed", "git_rebase_branch_executed", "git_rebase_interactive_executed", "git_rebase_continue_executed", "git_rebase_abort_executed", "git_cherry_pick_commit_executed", "git_fetch_executed", "git_pull_executed", "git_push_executed", "git_push_force_executed", "git_remote_add_executed", "git_remote_remove_executed", "git_stash_push_executed", "git_stash_pop_executed", "git_stash_list_shown", "git_stash_apply_executed", "git_tag_annotated_created", "git_tag_lightweight_created", "git_tag_delete_executed", "git_tag_list_shown", "git_reset_soft_executed", "git_reset_mixed_executed", "git_reset_hard_executed", "git_revert_commit_executed", "git_bisect_start_executed", "git_bisect_bad_executed", "git_bisect_good_executed", "git_bisect_reset_executed", "git_submodule_add_executed", "git_submodule_update_executed", "git_config_global_set", "git_config_local_set"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "gitcli" in title or "gitcli" in title or "git" in title

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
        return "git" in title
