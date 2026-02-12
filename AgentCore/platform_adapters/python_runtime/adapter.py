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


class PythonRuntimeAdapter(BaseAdapter):
    """Adapter for Python Runtime (local desktop application)."""

    EXE_HINT = "python.exe"

    @property
    def platform_name(self) -> str:
        return "Python Runtime"

    @property
    def supported_actions(self) -> List[str]:
        return ["script_executed", "interactive_shell_started", "module_imported", "pip_install_executed", "pip_uninstall_executed", "pip_list_shown", "pip_freeze_executed", "virtualenv_created", "virtualenv_activated", "virtualenv_deactivated", "package_built", "package_published", "unittest_run", "pytest_run", "pdb_debugger_started", "breakpoint_hit", "type_checking_executed", "linting_executed", "jupyter_notebook_started", "jupyter_cell_executed", "requirements_installed", "setup_py_executed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "pythonruntime" in title or "pythonruntime" in title or "python" in title

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
        return "python" in title
