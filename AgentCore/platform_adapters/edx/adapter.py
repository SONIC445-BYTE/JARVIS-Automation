from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class EdxAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "edX"

    @property
    def supported_actions(self) -> List[str]:
        return ["course_audited", "verified_certificate_purchased", "program_enrolled", "micromasters_started", "professional_certificate_earned", "proctored_exam_taken", "lab_completed", "peer_assessment_reviewed", "final_exam_passed", "transcript_downloaded", "discussion_forum_used", "wiki_contributed", "social_media_shared", "mobile_app_synced", "corporate_training_accessed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "edx" in title or "edx" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://edx.org/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
