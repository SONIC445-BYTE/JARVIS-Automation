from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class MondayAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Monday.com"

    @property
    def supported_actions(self) -> List[str]:
        return ["pulse_created", "column_customized", "status_updated", "automation_triggered", "integration_connected", "board_duplicated", "template_gallery_used", "workdoc_created", "gantt_chart_viewed", "dashboard_built", "team_member_invited", "guest_added", "notification_customized", "time_tracking_enabled", "inbox_zero_achieved"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "monday" in title or "monday" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://monday.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
