from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AzureAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Microsoft Azure"

    @property
    def supported_actions(self) -> List[str]:
        return ["virtual_machine_deployed", "function_app_created", "aks_cluster_provisioned", "app_service_published", "container_instance_run", "blob_storage_created", "managed_disk_attached", "file_share_mapped", "archive_tier_set", "data_lake_storage_gen2_enabled", "virtual_network_created", "network_security_group_configured", "application_gateway_deployed", "cdn_endpoint_created", "express_route_circuit_provisioned"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "azure" in title or "azure" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://azure.microsoft.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
