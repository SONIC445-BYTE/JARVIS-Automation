from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class MoodleAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Moodle"

    @property
    def supported_actions(self) -> List[str]:
        return ["resource_viewed", "activity_completed", "forum_posted", "wiki_edited", "glossary_entry_added", "quiz_attempted", "assignment_submitted", "workshop_peer_assessed", "lesson_completed", "scorm_package_tracked", "badge_awarded", "competency_achieved", "learning_plan_created", "cohort_joined", "mobile_app_offline_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "moodle" in title or "moodle" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://moodle.org/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
