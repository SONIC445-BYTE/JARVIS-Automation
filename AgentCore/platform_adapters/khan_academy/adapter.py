from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class KhanAcademyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Khan Academy"

    @property
    def supported_actions(self) -> List[str]:
        return ["video_watched", "exercise_completed", "article_read", "mission_started", "mastery_points_earned", "unit_test_taken", "course_challenge_attempted", "hint_used", "scratchpad_utilized", "coach_invited", "parent_account_linked", "teacher_dashboard_used", "class_code_joined", "discussion_participated", "badge_earned"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "khanacademy" in title or "khanacademy" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://khanacademy.org/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
