from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class UdemyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Udemy"

    @property
    def supported_actions(self) -> List[str]:
        return ["course_purchased", "lecture_completed", "note_taken", "q_and_a_asked", "certificate_downloaded", "coding_exercise_completed", "practice_test_taken", "progress_tracked", "lifetime_access_granted", "wishlist_added", "instructor_followed", "review_posted", "mobile_download_enabled", "business_account_managed", "learning_path_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "udemy" in title or "udemy" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://udemy.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
