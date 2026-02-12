from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PipedriveAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Pipedrive"

    @property
    def supported_actions(self) -> List[str]:
        return ["lead_captured", "deal_added", "activity_scheduled", "contact_mapped", "email_synced", "pipeline_stages_managed", "probability_updated", "forecast_viewed", "goal_set", "report_customized", "workflow_automation_triggered", "email_template_used", "web_form_submitted", "import_completed", "api_call_made"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "pipedrive" in title or "pipedrive" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://pipedrive.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
