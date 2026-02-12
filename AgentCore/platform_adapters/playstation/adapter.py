from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PlaystationAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "PlayStation Network"

    @property
    def supported_actions(self) -> List[str]:
        return ["trophy_earned", "game_downloaded", "remote_play_used", "share_play_initiated", "party_created", "community_joined", "broadcast_started", "messages_sent", "playstation_plus_subscribed", "wallet_funded", "pre_order_placed", "playstation_stars_enrolled"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "playstation" in title or "playstation" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://playstation.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
