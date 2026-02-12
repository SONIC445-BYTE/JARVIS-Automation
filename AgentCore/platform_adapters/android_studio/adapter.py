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


class AndroidStudioAdapter(BaseAdapter):
    """Adapter for Android Studio (local desktop application)."""

    EXE_HINT = "studio64.exe"

    @property
    def platform_name(self) -> str:
        return "Android Studio"

    @property
    def supported_actions(self) -> List[str]:
        return ["new_project_created", "new_module_added", "new_file_created", "new_class_created", "new_activity_created", "new_fragment_created", "new_service_created", "new_layout_file_created", "new_resource_file_created", "project_opened", "file_opened", "recent_project_opened", "project_imported", "file_saved", "all_files_saved", "file_closed", "project_closed", "file_renamed", "class_renamed", "method_renamed", "variable_renamed", "file_deleted", "file_moved", "file_copied", "code_typed", "paste_operation_executed", "undo_operation_executed", "redo_operation_executed", "reformat_code_executed", "optimize_imports_executed", "completion_basic_triggered", "completion_smart_type_triggered", "go_to_class_executed", "go_to_file_executed", "go_to_declaration_executed", "go_to_implementation_executed", "search_everywhere_opened", "find_in_path_executed", "find_usages_executed", "rename_refactoring_executed", "extract_method_refactoring_executed", "extract_variable_refactoring_executed", "inline_refactoring_executed", "generate_constructor_executed", "generate_getter_executed", "generate_setter_executed", "generate_override_methods_executed", "make_project_executed", "rebuild_project_executed", "clean_project_executed", "build_apk_executed", "generate_signed_bundle_or_apk_executed", "gradle_sync_started", "gradle_sync_finished_successfully", "run_app_executed", "debug_app_executed", "app_run_on_emulator", "app_run_on_physical_device", "virtual_device_created", "virtual_device_launched", "emulator_screen_capture_taken", "layout_editor_opened", "design_view_selected", "code_view_selected", "cpu_profiler_opened", "memory_profiler_opened", "network_profiler_opened", "database_inspector_opened", "layout_inspector_opened", "unit_test_run_executed", "unit_test_debug_executed", "git_commit_executed", "git_push_executed", "git_pull_executed", "git_branch_created", "git_merge_executed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "androidstudio" in title or "androidstudio" in title or "studio64" in title

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
        return "studio64" in title
