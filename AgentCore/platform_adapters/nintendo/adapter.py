from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class NintendoAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Nintendo eShop"

    @property
    def supported_actions(self) -> List[str]:
        return ["game_purchased", "wish_list_added", "gold_points_redeemed", "nintendo_switch_online_subscribed", "friend_code_exchanged", "screenshot_shared", "user_page_customized", "parental_controls_set", "nintendo_switch_expansion_pack_upgraded", "game_voucher_used", "dlc_purchased"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "nintendo" in title or "nintendo" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://nintendo.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
