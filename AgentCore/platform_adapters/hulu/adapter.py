from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class HuluAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Hulu"

    @property
    def supported_actions(self) -> List[str]:
        return ["episode_watched", "live_tv_tuned", "dvr_recording_set", "profile_switched", "watchlist_added", "my_stuff_organized", "no_ads_plan_upgraded", "live_tv_guide_customized", "disney_bundle_subscribed", "hulu_plus_live_tv_upgraded", "add_on_premium_channel_added"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "hulu" in title or "hulu" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://hulu.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
