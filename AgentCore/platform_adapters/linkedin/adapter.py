from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class LinkedinAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "LinkedIn"

    @property
    def supported_actions(self) -> List[str]:
        return ["post_shared", "article_published", "connection_request_sent", "job_applied", "endorsement_given", "recommendation_written", "event_registered", "learning_course_started", "sales_navigator_used", "recruiter_lite_used", "company_page_followed", "pulse_article_commented"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "linkedin" in title or "linkedin" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://linkedin.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
