from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class LyftAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Lyft"

    @property
    def supported_actions(self) -> List[str]:
        return ["ride_requested", "shared_ride_taken", "bike_scooter_unlocked", "scheduled_ride_set", "transit_info_viewed", "lyft_pink_subscribed", "bike_lane_navigation_used", "safety_features_used", "driver_tipped", "lost_item_reported", "rewards_points_earned", "challenge_completed", "partnership_perk_claimed", "business_profile_managed", "healthcare_ride_scheduled"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "lyft" in title or "lyft" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://lyft.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
