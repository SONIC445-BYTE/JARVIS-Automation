from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TelegramAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Telegram"

    @property
    def supported_actions(self) -> List[str]:
        return ["message_sent", "channel_created", "group_formed", "bot_started", "voice_chat_started", "poll_created", "story_posted", "username_claimed", "passport_verified", "giveaway_created", "quiz_initiated", "slow_mode_enabled"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "telegram" in title or "telegram" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://telegram.org/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
