from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SapSalesAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "SAP Sales Cloud"

    @property
    def supported_actions(self) -> List[str]:
        return ["lead_qualified", "account_360_viewed", "opportunity_managed", "quote_configured", "contract_executed", "sales_plan_activated", "territory_aligned", "forecast_committed", "sales_performance_managed", "rebate_program_executed", "workflow_triggered", "machine_learning_recommendation_used", "integration_flow_executed", "analytics_dashboard_viewed", "mobile_app_synced"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "sapsales" in title or "sap" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://sap.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
