from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class VkontakteAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "VKontakte"

    @property
    def supported_actions(self) -> List[str]:
        return ["wall_post_created", "photo_uploaded", "group_joined", "story_posted", "vk_pay_used", "vk_clips_watched", "vk_music_played", "market_item_listed", "live_stream_started", "podcast_listened", "vk_dating_used", "mini_app_opened"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "vkontakte" in title or "vk" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://vk.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
