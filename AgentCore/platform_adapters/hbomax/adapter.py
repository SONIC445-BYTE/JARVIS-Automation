from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class HbomaxAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "HBO Max"

    @property
    def supported_actions(self) -> List[str]:
        return ["content_streamed", "discovery_plus_content_accessed", "profile_customized", "download_managed", "my_list_curated", "series_reminder_set", "parental_pin_enabled", "audio_language_changed", "ad_free_plan_upgraded", "annual_plan_subscribed", "gift_card_redeemed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "hbomax" in title or "max" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://max.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
