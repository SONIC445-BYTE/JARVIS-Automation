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


class NodejsRuntimeAdapter(BaseAdapter):
    """Adapter for Node.js Runtime (local desktop application)."""

    EXE_HINT = "node.exe"

    @property
    def platform_name(self) -> str:
        return "Node.js Runtime"

    @property
    def supported_actions(self) -> List[str]:
        return ["script_executed", "repl_started", "npm_init_executed", "npm_install_executed", "npm_uninstall_executed", "npm_update_executed", "npm_run_script_executed", "npm_publish_executed", "npm_audit_executed", "npx_command_executed", "package_json_edited", "module_required", "module_imported_esm", "express_server_started", "http_server_started", "jest_test_run", "mocha_test_run", "webpack_build_executed", "vite_dev_server_started", "typescript_compiled", "eslint_executed", "nodemon_started", "pm2_process_managed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "nodejsruntime" in title or "node.jsruntime" in title or "node" in title

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
        return "node" in title
