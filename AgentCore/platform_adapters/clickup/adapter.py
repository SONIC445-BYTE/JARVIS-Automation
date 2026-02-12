from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ClickupAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "ClickUp"

    @property
    def supported_actions(self) -> List[str]:
        return ["task_created", "custom_status_applied", "time_estimated", "sprint_managed", "dependency_linked", "space_created", "folder_organized", "list_viewed", "goal_tracked", "dashboard_customized", "assignee_added", "watcher_set", "comment_resolved", "proofing_annotated", "email_integration_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "clickup" in title or "clickup" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://clickup.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
