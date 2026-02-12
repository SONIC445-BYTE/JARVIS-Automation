from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PardotAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Pardot"

    @property
    def supported_actions(self) -> List[str]:
        return ["campaign_launched", "landing_page_published", "form_handler_created", "dynamic_content_enabled", "engagement_program_built", "prospect_scored", "grading_profile_applied", "assignment_rule_triggered", "tag_added", "list_email_sent", "lifecycle_report_viewed", "roi_calculator_used", "connected_campaign_enabled", "einstein_behavior_scoring_viewed", "b2b_marketing_analytics_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "pardot" in title or "pardot" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://pardot.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
