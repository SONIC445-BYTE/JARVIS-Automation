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


class OnedriveAdapter(BaseAdapter):
    """Adapter for Microsoft OneDrive (local desktop application)."""

    EXE_HINT = "OneDrive.exe"

    @property
    def platform_name(self) -> str:
        return "Microsoft OneDrive"

    @property
    def supported_actions(self) -> List[str]:
        return ["file_uploaded", "folder_uploaded", "multiple_files_uploaded", "file_downloaded", "folder_downloaded", "file_synced_up", "file_synced_down", "file_sync_conflict_detected", "file_sync_conflict_resolved_keep_both", "file_sync_paused", "file_sync_resumed", "file_shared_link_created", "file_shared_link_deleted", "file_shared_link_permission_set_view", "file_shared_link_permission_set_edit", "file_shared_directly_to_user", "file_shared_to_group", "file_version_created", "file_version_restored", "folder_created", "folder_renamed", "folder_moved", "folder_deleted", "file_renamed", "file_moved", "file_deleted", "file_restored_from_recycle_bin", "file_search_executed", "file_filter_applied", "document_opened_for_editing", "document_edited_simultaneously_by_multiple_users", "comment_added", "comment_resolved", "file_sync_on_demand_files_enabled", "file_sync_free_up_space_used", "user_signed_in", "user_signed_out", "retention_policy_applied", "dlp_policy_triggered"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "onedrive" in title or "microsoftonedrive" in title or "onedrive" in title

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
        return "onedrive" in title
