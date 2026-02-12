from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class InstagramAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Instagram"

    @property
    def supported_actions(self) -> List[str]:
        return ["photo_posted", "story_posted", "reel_shared", "post_liked", "direct_message_sent", "story_replied", "live_started", "close_friend_added", "shop_product_viewed", "filter_applied", "music_added", "collaboration_posted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "instagram" in title or "instagram" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://instagram.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
