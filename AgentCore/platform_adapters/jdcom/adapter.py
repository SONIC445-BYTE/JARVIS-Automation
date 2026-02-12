from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class JdcomAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "JD.com"

    @property
    def supported_actions(self) -> List[str]:
        return ["product_searched", "flash_sale_joined", "plus_membership_subscribed", "group_buy_initiated", "store_opened", "jd_logistics_used", "jd_cloud_service_accessed", "advertising_purchased", "jd_health_consulted", "jd_finance_used", "jd_property_viewed", "jd_auction_participated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "jdcom" in title or "jd" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://jd.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
