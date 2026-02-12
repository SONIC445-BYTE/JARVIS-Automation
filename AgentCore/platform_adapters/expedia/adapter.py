from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ExpediaAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Expedia"

    @property
    def supported_actions(self) -> List[str]:
        return ["flight_booked", "hotel_reserved", "package_purchased", "activity_booked", "cruise_reserved", "itinerary_viewed", "price_drop_alert_set", "loyalty_points_redeemed", "mobile_exclusive_deal_claimed", "travel_insurance_added", "expedia_rewards_enrolled", "gold_status_achieved", "vip_access_property_booked", "member_price_used", "point_purchase_made"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "expedia" in title or "expedia" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://expedia.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
