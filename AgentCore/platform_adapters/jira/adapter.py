from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class JiraAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Jira"

    @property
    def supported_actions(self) -> List[str]:
        return ["issue_created", "sprint_started", "epic_linked", "story_point_estimated", "bug_reported", "project_configured", "workflow_customized", "scrum_board_managed", "kanban_used", "roadmap_planned", "developer_assigned", "watcher_added", "comment_logged", "attachment_added", "time_logged"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "jira" in title or "atlassian" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://atlassian.net/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
