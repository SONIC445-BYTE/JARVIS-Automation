from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class StravaAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Strava"

    @property
    def supported_actions(self) -> List[str]:
        return ["activity_recorded", "route_planned", "segment_raced", "kudos_given", "club_joined", "gear_logged", "training_log_updated", "fitness_freshness_tracked", "relative_effort_calculated", "power_curve_analyzed", "beacon_enabled", "route_shared", "subscription_upgraded", "summit_feature_used", "partner_perk_claimed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "strava" in title or "strava" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://strava.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
