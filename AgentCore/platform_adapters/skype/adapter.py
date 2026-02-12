from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SkypeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Skype"

    @property
    def supported_actions(self) -> List[str]:
        return ["call_initiated", "video_enabled", "group_call_started", "message_recorded", "effect_applied", "screen_shared", "contact_invited", "call_history_cleared"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "skype" in title or "skype" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://skype.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
