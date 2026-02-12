from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BlackboardAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Blackboard"

    @property
    def supported_actions(self) -> List[str]:
        return ["content_item_opened", "assignment_uploaded", "test_submitted", "discussion_board_posted", "journal_entry_created", "safeassign_report_viewed", "rubric_assessed", "attempt_graded", "feedback_released", "external_tool_launched", "course_announcement_received", "email_sent", "group_workspace_accessed", "mobile_app_logged_in", "student_preview_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "blackboard" in title or "blackboard" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://blackboard.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
