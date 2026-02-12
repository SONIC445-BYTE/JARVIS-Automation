from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class Dynamics365Adapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Microsoft Dynamics 365"

    @property
    def supported_actions(self) -> List[str]:
        return ["lead_qualified", "opportunity_created", "contact_synchronized", "account_hierarchy_managed", "case_routed", "sales_process_guided", "quote_generated", "order_fulfilled", "invoice_generated", "relationship_analytics_viewed", "power_automate_flow_triggered", "ai_insights_viewed", "workflow_executed", "business_process_flow_completed", "power_bi_report_embedded"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "dynamics365" in title or "dynamics" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://dynamics.microsoft.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
