from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SnapchatAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Snapchat"

    @property
    def supported_actions(self) -> List[str]:
        return ["snap_sent", "story_posted", "streak_maintained", "filter_applied", "spotlight_viewed", "map_location_shared", "bitmoji_customized", "memory_saved", "snapcash_sent", "lens_created", "discover_subscribed", "friendship_profile_viewed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "snapchat" in title or "snapchat" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://snapchat.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
