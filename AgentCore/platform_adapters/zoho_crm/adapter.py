from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ZohoCrmAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Zoho CRM"

    @property
    def supported_actions(self) -> List[str]:
        return ["lead_converted", "account_hierarchy_managed", "contact_enriched", "potential_created", "case_resolved", "blueprint_executed", "canvas_view_designed", "forecast_adjusted", "territory_assigned", "social_twitter_integrated", "workflow_rule_triggered", "scheduled_function_executed", "web_form_captured", "email_sent", "zia_ai_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "zohocrm" in title or "zoho" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://zoho.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
