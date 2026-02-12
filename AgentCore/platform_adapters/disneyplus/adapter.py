from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class DisneyplusAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Disney+"

    @property
    def supported_actions(self) -> List[str]:
        return ["title_played", "groupwatch_started", "download_added", "continue_watching_resumed", "profile_created", "parental_controls_set", "watchlist_added", "star_content_enabled", "bundle_subscribed", "premier_access_purchased", "gift_subscription_sent"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "disneyplus" in title or "disneyplus" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://disneyplus.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
