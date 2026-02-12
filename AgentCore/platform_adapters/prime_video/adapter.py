from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PrimeVideoAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Amazon Prime Video"

    @property
    def supported_actions(self) -> List[str]:
        return ["title_streamed", "channel_subscribed", "video_purchased", "rent_completed", "watchlist_managed", "x_ray_feature_used", "imdb_integration_viewed", "audio_description_enabled", "prime_membership_managed", "video_direct_publishing_used", "amazon_channels_managed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "primevideo" in title or "primevideo" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://primevideo.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
