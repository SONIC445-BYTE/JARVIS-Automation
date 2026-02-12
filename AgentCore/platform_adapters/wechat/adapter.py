from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class WechatAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "WeChat"

    @property
    def supported_actions(self) -> List[str]:
        return ["moment_posted", "mini_program_opened", "payment_made", "official_account_followed", "red_packet_sent", "sticker_purchased", "top_story_read", "wechat_pay_used", "channel_live_started", "video_call_group_started", "favorites_added", "people_nearby_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "wechat" in title or "wechat" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://wechat.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
