from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BumbleAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Bumble"

    @property
    def supported_actions(self) -> List[str]:
        return ["profile_created", "swipe_right", "swipe_left", "match_made", "message_sent", "super_like_used", "boost_applied", "date_scheduled"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "bumble" in title or "bumble" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://bumble.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
