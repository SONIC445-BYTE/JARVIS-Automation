
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class ExplorerAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Windows Explorer"

    @property
    def supported_actions(self) -> List[str]:
        return ["open_folder"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        # Hard to detect generically without class name check via pywinauto
        title = ui_tree.get("active_window", "")
        return True # Plausible fallback for now

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "open_folder":
            path = params.get("path", "C:\\")
            steps.append(ExecutionStep(action="open_app", target=path, parameters={"app_name": "explorer"}))
                
        return Plan(steps=steps, confidence=0.95)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
