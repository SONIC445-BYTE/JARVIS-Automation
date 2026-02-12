from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class GoogleClassroomAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Google Classroom"

    @property
    def supported_actions(self) -> List[str]:
        return ["class_joined", "assignment_viewed", "work_submitted", "material_accessed", "question_posted", "assignment_returned", "grade_posted", "originality_report_viewed", "rubric_graded", "late_work_flagged", "announcement_created", "meet_link_generated", "guardian_summary_enabled", "calendar_synced", "drive_folder_organized"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "googleclassroom" in title or "classroom" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://classroom.google.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
