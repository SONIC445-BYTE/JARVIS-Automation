from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class EpicGamesAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Epic Games Store"

    @property
    def supported_actions(self) -> List[str]:
        return ["free_game_claimed", "purchase_made", "library_managed", "download_scheduled", "friend_added", "party_formed", "voice_chat_used", "screenshot_shared", "creator_code_used", "epic_coupon_applied", "refund_requested", "supporter_pack_purchased"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "epicgames" in title or "store" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://store.epicgames.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
