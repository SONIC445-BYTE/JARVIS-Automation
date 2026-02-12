from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class DiscordAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Discord"

    @property
    def supported_actions(self) -> List[str]:
        return ["message_sent", "server_joined", "channel_created", "role_assigned", "nitro_subscribed", "boost_applied", "stage_channel_started", "thread_created", "slash_command_used", "bot_added", "emoji_uploaded", "server_template_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "discord" in title or "discord" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://discord.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
