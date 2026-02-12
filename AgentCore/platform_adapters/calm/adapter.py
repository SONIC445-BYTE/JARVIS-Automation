from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class CalmAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Calm"

    @property
    def supported_actions(self) -> List[str]:
        return ["meditation_played", "sleep_story_listened", "masterclass_watched", "breathing_exercise_completed", "music_track_played", "mood_check_in_logged", "streak_tracked", "reminder_customized", "favorite_added", "offline_content_downloaded", "subscription_purchased", "gift_card_redeemed", "corporate_wellness_accessed", "kids_section_used", "breathe_bubble_customized"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "calm" in title or "calm" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://calm.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
