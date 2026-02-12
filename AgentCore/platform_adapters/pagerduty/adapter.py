from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PagerdutyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "PagerDuty"

    @property
    def supported_actions(self) -> List[str]:
        return ["service_created", "escalation_policy_configured", "schedule_managed", "integration_added", "automation_action_created", "incident_triggered", "on_call_rotation_started", "status_update_published", "post_mortem_documented", "business_service_mapped", "event_intelligence_used", "automation_triggered", "permissions_managed", "audit_log_reviewed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "pagerduty" in title or "pagerduty" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://pagerduty.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
