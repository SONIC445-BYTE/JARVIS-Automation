from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TrelloAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Trello"

    @property
    def supported_actions(self) -> List[str]:
        return ["card_created", "checklist_added", "label_applied", "due_date_reminder_set", "attachment_uploaded", "board_created", "power_up_enabled", "automation_rule_set", "template_applied", "workspace_managed", "member_invited", "card_shared", "voting_initiated", "calendar_view_enabled", "dashboard_viewed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "trello" in title or "trello" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://trello.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
