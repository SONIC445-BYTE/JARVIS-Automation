
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class ChromeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Google Chrome"

    @property
    def supported_actions(self) -> List[str]:
        return ["open_url", "new_tab", "close_tab"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "chrome" in title or "edge" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "open_url":
            url = params.get("url", "")
            steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
            
        elif action_name == "new_tab":
            steps.append(ExecutionStep(action="press_key", target="ctrl+t", parameters={"key": "t", "modifiers": ["ctrl"]}))
            
        elif action_name == "close_tab":
            steps.append(ExecutionStep(action="press_key", target="ctrl+w", parameters={"key": "w", "modifiers": ["ctrl"]}))
                
        return Plan(steps=steps, confidence=0.9)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
