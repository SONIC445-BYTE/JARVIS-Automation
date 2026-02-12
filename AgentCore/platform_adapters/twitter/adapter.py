
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TwitterAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Twitter/X"

    @property
    def supported_actions(self) -> List[str]:
        return ["post_tweet"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "twitter" in title or "x" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "post_tweet":
            text = urllib.parse.quote(params.get("text", ""))
            url = f"https://twitter.com/intent/tweet?text={text}"
            steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
            
        return Plan(steps=steps, confidence=0.9)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
