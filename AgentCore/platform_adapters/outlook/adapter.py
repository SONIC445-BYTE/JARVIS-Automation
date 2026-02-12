from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class OutlookAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Outlook"

    @property
    def supported_actions(self) -> List[str]:
        return ["email_composed", "email_sent", "email_opened", "attachment_added", "label_applied", "filter_created", "vacation_responder_enabled", "signature_updated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "outlook" in title or "outlook" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://outlook.live.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
