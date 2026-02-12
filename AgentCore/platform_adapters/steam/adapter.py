from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SteamAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Steam"

    @property
    def supported_actions(self) -> List[str]:
        return ["game_purchased", "library_organized", "achievement_unlocked", "cloud_save_synced", "friend_invited", "group_joined", "review_posted", "workshop_item_subscribed", "broadcast_watched", "steam_wallet_funded", "market_transaction_completed", "trading_card_exchanged", "hardware_purchased"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "steam" in title or "store" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://store.steampowered.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
