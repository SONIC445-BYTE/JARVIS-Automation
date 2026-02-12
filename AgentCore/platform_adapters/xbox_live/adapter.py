from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class XboxLiveAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Xbox Live"

    @property
    def supported_actions(self) -> List[str]:
        return ["game_pass_game_installed", "achievement_earned", "gamerscore_increased", "cloud_gaming_used", "party_chat_joined", "looking_for_group_posted", "club_joined", "activity_feed_updated", "microsoft_points_redeemed", "game_pass_subscription_managed", "xbox_design_lab_used", "elite_controller_customized"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "xboxlive" in title or "xbox" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://xbox.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
