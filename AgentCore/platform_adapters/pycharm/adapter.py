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


class PycharmAdapter(BaseAdapter):
    """Adapter for PyCharm (local desktop application)."""

    EXE_HINT = "pycharm64.exe"

    @property
    def platform_name(self) -> str:
        return "PyCharm"

    @property
    def supported_actions(self) -> List[str]:
        return ["new_project_created", "new_file_created", "new_python_file_created", "new_python_package_created", "new_jupyter_notebook_created", "project_opened", "file_opened", "file_saved", "file_closed", "file_renamed", "file_moved", "file_deleted", "code_completion_basic_invoked", "code_completion_smart_invoked", "quick_fix_applied", "intention_action_executed", "go_to_declaration_executed", "go_to_implementation_executed", "go_to_class_executed", "go_to_file_executed", "go_to_symbol_executed", "search_everywhere_opened", "find_in_path_executed", "find_usages_executed", "rename_refactoring_executed", "extract_method_executed", "extract_variable_executed", "inline_refactoring_executed", "reformat_code_executed", "optimize_imports_executed", "run_configuration_executed", "debug_configuration_executed", "breakpoint_toggled", "step_over_executed", "step_into_executed", "evaluate_expression_executed", "watch_added", "python_interpreter_configured", "virtualenv_created", "pip_package_installed", "pip_package_uninstalled", "pytest_run_executed", "unittest_run_executed", "coverage_analysis_run", "test_results_viewed", "git_commit_executed", "git_push_executed", "git_pull_executed", "git_branch_created", "git_merge_executed", "terminal_opened", "python_console_opened", "jupyter_notebook_cell_executed", "jupyter_kernel_restarted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "pycharm" in title or "pycharm" in title or "pycharm64" in title

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
        return "pycharm64" in title
