from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class MailchimpAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Mailchimp"

    @property
    def supported_actions(self) -> List[str]:
        return ["campaign_created", "audience_segmented", "template_designed", "automation_configured", "landing_page_published", "subscriber_imported", "tag_applied", "signup_form_embedded", "preference_center_customized", "cleaning_recommended", "report_viewed", "a_b_test_analyzed", "send_time_optimization_used", "comparative_report_generated", "social_post_scheduled"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "mailchimp" in title or "mailchimp" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://mailchimp.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
