from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SchoologyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Schoology"

    @property
    def supported_actions(self) -> List[str]:
        return ["course_material_accessed", "assignment_submitted", "test_completed", "discussion_participated", "folder_created", "grade_viewed", "attendance_marked", "learning_objective_mastered", "mastery_report_generated", "portfolio_assembled", "message_sent", "group_joined", "calendar_event_added", "resource_appended", "parent_access_granted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "schoology" in title or "schoology" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://schoology.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
