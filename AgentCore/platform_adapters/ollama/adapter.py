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


class OllamaAdapter(BaseAdapter):
    """Adapter for Ollama (local desktop application)."""

    EXE_HINT = "ollama.exe"

    @property
    def platform_name(self) -> str:
        return "Ollama"

    @property
    def supported_actions(self) -> List[str]:
        return ["model_pulled", "model_removed", "model_list_shown", "model_run_started", "model_run_stopped", "chat_message_sent", "chat_response_received", "api_server_started", "api_request_processed", "modelfile_created", "custom_model_built", "model_copied", "model_pushed", "system_prompt_set", "temperature_set", "embedding_generated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "ollama" in title or "ollama" in title or "ollama" in title

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
        return "ollama" in title
