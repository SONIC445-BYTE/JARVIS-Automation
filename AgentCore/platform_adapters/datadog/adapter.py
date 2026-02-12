from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class DatadogAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Datadog"

    @property
    def supported_actions(self) -> List[str]:
        return ["agent_installed", "dashboard_created", "monitor_configured", "log_pipeline_set_up", "apm_instrumented", "alert_triggered", "synthetic_test_created", "rum_session_replay_viewed", "slo_defined", "incident_declared", "security_signal_investigated", "compliance_monitor_enabled", "cloud_security_posture_managed", "application_vulnerability_detected"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "datadog" in title or "datadoghq" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://datadoghq.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
