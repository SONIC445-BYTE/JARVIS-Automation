from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class JenkinsAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Jenkins"

    @property
    def supported_actions(self) -> List[str]:
        return ["job_created", "build_triggered", "pipeline_scripted", "plugin_installed", "node_configured", "deployment_stage_executed", "artifact_archived", "test_report_generated", "credential_managed", "backup_scheduled", "user_permission_assigned", "audit_trail_reviewed", "distributed_build_configured", "cloud_agent_provisioned", "update_center_accessed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "jenkins" in title or "jenkins" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://jenkins.io/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
