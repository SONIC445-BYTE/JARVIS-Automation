from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class UberAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Uber"

    @property
    def supported_actions(self) -> List[str]:
        return ["ride_requested", "trip_completed", "fare_split", "scheduled_ride_set", "pool_joined", "uber_eats_ordered", "freight_shipment_created", "business_profile_switched", "safety_toolkit_used", "rating_given", "uber_rewards_enrolled", "uber_cash_purchased", "uber_pass_subscribed", "vip_support_accessed", "jump_bike_rented"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "uber" in title or "uber" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://uber.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
