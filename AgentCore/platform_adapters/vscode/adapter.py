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


class VscodeAdapter(BaseAdapter):
    """Adapter for VS Code (local desktop application)."""

    EXE_HINT = "code.exe"

    @property
    def platform_name(self) -> str:
        return "VS Code"

    @property
    def supported_actions(self) -> List[str]:
        return ["new_file_created", "new_folder_created", "new_workspace_created", "file_opened", "file_saved", "file_saved_as", "file_closed", "file_renamed", "file_moved", "file_deleted", "text_typed", "text_pasted", "text_cut", "text_copied", "undo_executed", "redo_executed", "find_executed", "replace_executed", "find_in_files_executed", "go_to_file_executed", "go_to_symbol_executed", "go_to_line_executed", "go_to_definition_executed", "go_to_references_executed", "peek_definition_executed", "peek_references_executed", "code_completion_triggered", "quick_fix_applied", "rename_symbol_executed", "extract_method_executed", "format_document_executed", "format_selection_executed", "toggle_comment_executed", "toggle_block_comment_executed", "extension_installed", "extension_uninstalled", "extension_updated", "terminal_opened", "terminal_command_executed", "debug_session_started", "breakpoint_toggled", "git_stage_executed", "git_commit_executed", "git_push_executed", "git_pull_executed", "git_branch_created", "git_checkout_executed", "task_run_executed", "settings_changed", "keybinding_changed", "snippet_inserted", "emmet_expanded", "split_editor_opened", "editor_group_created", "command_palette_opened", "workspace_settings_changed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "vscode" in title or "vscode" in title or "code" in title

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
        return "code" in title
