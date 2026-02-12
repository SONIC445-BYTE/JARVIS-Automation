from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class QqAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "QQ"

    @property
    def supported_actions(self) -> List[str]:
        return ["message_sent", "qzone_posted", "group_joined", "file_transferred", "qq_wallet_used", "qq_music_played", "qq_game_launched", "qq_mail_sent", "qq_live_watched", "qq_read_used", "qq_shopping_visited", "qq_health_synced"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "qq" in title or "qq" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://qq.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
