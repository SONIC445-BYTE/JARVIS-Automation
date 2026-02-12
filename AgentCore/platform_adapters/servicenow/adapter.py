from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ServicenowAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "ServiceNow"

    @property
    def supported_actions(self) -> List[str]:
        return ["instance_requested", "application_installed", "workflow_created", "catalog_item_published", "integration_hub_spoke_used", "incident_created", "problem_investigated", "change_request_approved", "service_catalog_ordered", "cmdb_populated", "security_incident_responded", "vulnerability_response_managed", "grc_control_attested", "soar_playbook_executed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "servicenow" in title or "servicenow" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://servicenow.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
