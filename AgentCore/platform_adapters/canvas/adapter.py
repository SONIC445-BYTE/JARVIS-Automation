from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class CanvasAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Canvas"

    @property
    def supported_actions(self) -> List[str]:
        return ["course_accessed", "assignment_submitted", "module_completed", "collaboration_used", "eportfolio_created", "quiz_taken", "rubric_viewed", "feedback_received", "gradebook_checked", "late_policy_applied", "announcement_read", "calendar_event_added", "conference_joined", "mobile_notification_received", "parent_observer_added"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "canvas" in title or "instructure" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://instructure.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
