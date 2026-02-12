from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BasecampAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Basecamp"

    @property
    def supported_actions(self) -> List[str]:
        return ["to_do_list_created", "message_board_posted", "schedule_added", "document_uploaded", "automatic_check_in_set", "project_created", "hill_chart_updated", "client_access_enabled", "template_project_used", "progress_reported", "person_invited", "ping_sent", "campfire_chat_used", "doorbell_rung", "boost_given"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "basecamp" in title or "basecamp" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://basecamp.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
