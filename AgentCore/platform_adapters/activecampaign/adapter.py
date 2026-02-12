from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ActivecampaignAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "ActiveCampaign"

    @property
    def supported_actions(self) -> List[str]:
        return ["automation_built", "campaign_sent", "deal_created", "chat_conversation_started", "site_tracking_enabled", "contact_tagged", "list_managed", "form_submitted", "goal_achieved", "sms_sent", "report_analyzed", "split_test_reviewed", "attribution_tracked", "predictive_sending_used", "crm_synced"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "activecampaign" in title or "activecampaign" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://activecampaign.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
