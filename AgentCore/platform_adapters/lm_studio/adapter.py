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


class LmStudioAdapter(BaseAdapter):
    """Adapter for LM Studio (local desktop application)."""

    EXE_HINT = "LM Studio.exe"

    @property
    def platform_name(self) -> str:
        return "LM Studio"

    @property
    def supported_actions(self) -> List[str]:
        return ["model_downloaded", "model_loaded", "model_unloaded", "chat_session_started", "chat_message_sent", "chat_response_received", "system_prompt_set", "temperature_adjusted", "max_tokens_set", "local_server_started", "local_server_stopped", "api_endpoint_configured", "model_quantization_selected", "context_length_set", "gpu_layers_configured", "chat_history_exported"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "lmstudio" in title or "lmstudio" in title or "lm studio" in title

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
        return "lm studio" in title
