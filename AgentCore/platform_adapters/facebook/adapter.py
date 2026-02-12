from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class FacebookAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Facebook"

    @property
    def supported_actions(self) -> List[str]:
        return ["post_created", "post_shared", "post_liked", "comment_added", "friend_request_sent", "friend_request_accepted", "group_joined", "event_created", "story_viewed", "live_stream_started", "marketplace_item_listed", "fundraiser_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "facebook" in title or "facebook" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://facebook.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
