from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class LineAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "LINE"

    @property
    def supported_actions(self) -> List[str]:
        return ["message_sent", "timeline_posted", "sticker_purchased", "official_account_added", "line_pay_used", "line_music_played", "line_manga_read", "line_taxi_called", "openchat_joined", "line_shopping_used", "line_game_played", "line_tv_watched"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "line" in title or "line" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://line.me/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
