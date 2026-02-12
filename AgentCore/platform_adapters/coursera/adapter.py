from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class CourseraAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Coursera"

    @property
    def supported_actions(self) -> List[str]:
        return ["course_enrolled", "lecture_watched", "reading_completed", "peer_review_submitted", "certificate_earned", "quiz_attempted", "programming_assignment_submitted", "exam_proctored", "grade_received", "mastery_achieved", "discussion_posted", "mentor_consulted", "study_group_joined", "mobile_app_downloaded", "degree_applied"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "coursera" in title or "coursera" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://coursera.org/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
