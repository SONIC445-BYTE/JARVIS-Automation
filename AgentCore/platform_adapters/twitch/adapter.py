from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TwitchAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Twitch"

    @property
    def supported_actions(self) -> List[str]:
        return ["stream_watched", "follow_clicked", "subscription_gifted", "bits_cheered", "channel_points_redeemed", "raid_initiated", "clip_created", "extension_interacted", "prediction_participated", "turbo_subscription_purchased", "gifted_sub_sent", "bits_purchased", "hype_train_contributed", "creator_camp_completed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "twitch" in title or "twitch" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://twitch.tv/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
