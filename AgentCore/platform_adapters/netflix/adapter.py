from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class NetflixAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Netflix"

    @property
    def supported_actions(self) -> List[str]:
        return ["title_played", "episode_completed", "season_binged", "download_initiated", "profile_switched", "my_list_added", "rating_given", "subtitle_preference_set", "playback_speed_changed", "subscription_upgraded", "dvd_plan_added", "gift_card_redeemed", "extra_member_added"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "netflix" in title or "netflix" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://netflix.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
