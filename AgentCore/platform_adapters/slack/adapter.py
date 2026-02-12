from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SlackAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Slack"

    @property
    def supported_actions(self) -> List[str]:
        return ["workspace_created", "channel_joined", "message_threaded", "file_uploaded", "integration_added", "workflow_automated", "huddle_started", "canvas_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "slack" in title or "slack" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://slack.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
