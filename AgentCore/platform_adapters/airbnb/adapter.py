from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AirbnbAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Airbnb"

    @property
    def supported_actions(self) -> List[str]:
        return ["listing_searched", "booking_requested", "reservation_confirmed", "check_in_completed", "review_left", "experience_booked", "wishlist_created", "co_host_invited", "guidebook_accessed", "message_sent", "superguest_status_earned", "referral_credit_earned", "airbnb_plus_explored", "luxe_property_viewed", "long_term_stay_discount_applied"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "airbnb" in title or "airbnb" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://airbnb.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
