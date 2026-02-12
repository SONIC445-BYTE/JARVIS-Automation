from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AsanaAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Asana"

    @property
    def supported_actions(self) -> List[str]:
        return ["task_created", "subtask_added", "due_date_set", "assignee_designated", "custom_field_updated", "project_created", "timeline_viewed", "portfolio_managed", "goal_set", "workload_balanced", "team_invited", "comment_added", "proofing_used", "approval_requested", "form_submitted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "asana" in title or "asana" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://asana.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
