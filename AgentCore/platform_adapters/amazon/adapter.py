
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AmazonAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Amazon"

    @property
    def supported_actions(self) -> List[str]:
        return ["search_product"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "amazon" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "search_product":
            query = urllib.parse.quote(params.get("query", ""))
            url = f"https://www.amazon.com/s?k={query}"
            steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
            
        return Plan(steps=steps, confidence=0.95)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
