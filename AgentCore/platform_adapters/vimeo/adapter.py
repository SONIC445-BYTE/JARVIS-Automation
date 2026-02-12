from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class VimeoAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Vimeo"

    @property
    def supported_actions(self) -> List[str]:
        return ["video_uploaded", "portfolio_created", "review_page_shared", "live_event_streamed", "video_replaced", "privacy_settings_adjusted", "custom_player_embedded", "analytics_reviewed", "vimeo_plus_upgraded", "vimeo_pro_subscribed", "vimeo_business_enrolled", "ott_platform_launched", "stock_footage_purchased"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "vimeo" in title or "vimeo" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://vimeo.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
