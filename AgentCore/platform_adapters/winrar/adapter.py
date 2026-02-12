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


class WinrarAdapter(BaseAdapter):
    """Adapter for WinRAR (local desktop application)."""

    EXE_HINT = "WinRAR.exe"

    @property
    def platform_name(self) -> str:
        return "WinRAR"

    @property
    def supported_actions(self) -> List[str]:
        return ["archive_created", "archive_opened", "archive_extracted", "files_added_to_archive", "files_deleted_from_archive", "archive_tested", "archive_repaired", "compression_method_selected_store", "compression_method_selected_fastest", "compression_method_selected_normal", "compression_method_selected_best", "archive_format_rar_selected", "archive_format_zip_selected", "password_protection_applied", "split_archive_created", "self_extracting_archive_created", "comment_added_to_archive"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "winrar" in title or "winrar" in title or "winrar" in title

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
        return "winrar" in title
