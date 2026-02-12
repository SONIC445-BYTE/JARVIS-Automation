from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BookingAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Booking.com"

    @property
    def supported_actions(self) -> List[str]:
        return ["property_searched", "reservation_made", "modification_requested", "cancellation_processed", "review_posted", "genius_program_joined", "trip_planner_used", "airport_transfer_booked", "car_rental_reserved", "flight_searched", "genius_level_achieved", "reward_claimed", "mobile_app_exclusive_used", "secret_deal_unlocked", "partner_offer_redeemed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "booking" in title or "booking" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://booking.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
