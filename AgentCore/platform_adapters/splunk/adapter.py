from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SplunkAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Splunk"

    @property
    def supported_actions(self) -> List[str]:
        return ["forwarder_installed", "index_created", "search_head_cluster_deployed", "dashboard_published", "alert_configured", "search_ran", "report_scheduled", "machine_learning_model_applied", "it_service_intelligence_enabled", "phantom_playbook_executed", "security_event_investigated", "user_behavior_analytics_enabled", "risk_score_calculated", "compliance_report_generated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "splunk" in title or "splunk" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://splunk.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
