from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class RobloxAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Roblox"

    @property
    def supported_actions(self) -> List[str]:
        return ["game_joined", "avatar_customized", "place_created", "robux_earned", "friend_request_sent", "group_joined", "private_server_created", "trade_request_sent", "robux_purchased", "premium_subscription_purchased", "game_pass_sold", "developer_exchange_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "roblox" in title or "roblox" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://roblox.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
