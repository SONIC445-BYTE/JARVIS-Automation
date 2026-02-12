from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class WalmartAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Walmart Marketplace"

    @property
    def supported_actions(self) -> List[str]:
        return ["product_listed", "fulfillment_service_used", "advertising_campaign_managed", "return_processed", "seller_account_approved", "walmart_fulfillment_services_enrolled", "repricer_tool_used", "performance_metrics_viewed", "pro_seller_badge_earned", "walmart_connect_advertising_used", "seller_support_ticket_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "walmart" in title or "walmart" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://walmart.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
