from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SmartsheetAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Smartsheet"

    @property
    def supported_actions(self) -> List[str]:
        return ["row_added", "column_formula_created", "gantt_chart_enabled", "card_view_used", "form_connected", "workspace_created", "template_applied", "automation_workflow_built", "dashboard_widget_added", "report_scheduled", "collaborator_invited", "proofing_requested", "update_request_sent", "publish_enabled", "calendar_integrated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "smartsheet" in title or "smartsheet" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://smartsheet.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
