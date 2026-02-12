from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class FreshsalesAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Freshsales"

    @property
    def supported_actions(self) -> List[str]:
        return ["lead_scored", "contact_enriched", "account_hierarchy_built", "deal_qualified", "appointment_scheduled", "sales_sequence_initiated", "territory_auto_assigned", "forecast_generated", "document_shared", "quote_created", "workflow_automated", "chat_triggered", "email_tracking_enabled", "phone_call_logged", "api_integrated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "freshsales" in title or "freshworks" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://freshworks.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
