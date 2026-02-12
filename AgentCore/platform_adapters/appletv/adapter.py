from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AppletvAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Apple TV+"

    @property
    def supported_actions(self) -> List[str]:
        return ["original_watched", "family_sharing_enabled", "download_saved", "up_next_added", "apple_tv_channel_subscribed", "itunes_movie_purchased", "library_synced", "airplay_used", "apple_one_bundle_subscribed", "apple_tv_plus_free_trial_started", "apple_gift_card_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "appletv" in title or "tv" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://tv.apple.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
