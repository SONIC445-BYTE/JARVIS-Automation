
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class CalculatorAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Calculator"

    @property
    def supported_actions(self) -> List[str]:
        return ["calculate"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "calculator" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "calculate":
            expression = params.get("expression", "")
            steps.append(ExecutionStep(action="type", target=expression, parameters={"text": expression}))
            steps.append(ExecutionStep(action="press_key", target="enter", parameters={"key": "enter"}))
                
        return Plan(steps=steps, confidence=0.9)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
