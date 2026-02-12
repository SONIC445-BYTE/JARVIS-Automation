from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class CircleciAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "CircleCI"

    @property
    def supported_actions(self) -> List[str]:
        return ["config_validated", "workflow_triggered", "orb_used", "context_created", "schedule_configured", "docker_image_built", "kubernetes_deployment_made", "artifact_stored", "test_parallelization_run", "security_scan_integrated", "team_member_invited", "project_followed", "insights_viewed", "plan_upgraded", "support_ticket_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "circleci" in title or "circleci" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://circleci.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
