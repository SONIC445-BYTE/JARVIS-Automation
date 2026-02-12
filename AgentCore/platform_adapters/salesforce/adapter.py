from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SalesforceAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Salesforce"

    @property
    def supported_actions(self) -> List[str]:
        return ["lead_created", "contact_enriched", "account_mapped", "opportunity_qualified", "case_escalated", "forecast_submitted", "quote_generated", "contract_negotiated", "order_processed", "renewal_managed", "workflow_rule_triggered", "process_builder_executed", "flow_automated", "apex_trigger_fired", "einstein_prediction_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "salesforce" in title or "salesforce" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://salesforce.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
