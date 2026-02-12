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


class ArduinoIdeAdapter(BaseAdapter):
    """Adapter for Arduino IDE (local desktop application)."""

    EXE_HINT = "arduino.exe"

    @property
    def platform_name(self) -> str:
        return "Arduino IDE"

    @property
    def supported_actions(self) -> List[str]:
        return ["new_sketch_created", "sketch_opened", "sketch_saved", "sketch_saved_as", "sketch_closed", "example_sketch_opened", "code_typed", "code_pasted", "undo_executed", "redo_executed", "verify_compile_executed", "upload_executed", "upload_using_programmer_executed", "board_selected", "port_selected", "programmer_selected", "library_installed", "library_removed", "library_updated", "board_manager_opened", "board_package_installed", "serial_monitor_opened", "serial_plotter_opened", "serial_data_sent", "baud_rate_changed", "preferences_changed", "verbose_output_enabled", "include_library_added", "sketch_exported_compiled_binary"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "arduinoide" in title or "arduinoide" in title or "arduino" in title

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
        return "arduino" in title
