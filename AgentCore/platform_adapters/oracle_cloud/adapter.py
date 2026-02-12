from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class OracleCloudAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Oracle Cloud"

    @property
    def supported_actions(self) -> List[str]:
        return ["compute_instance_launched", "function_deployed", "container_engine_kubernetes_cluster_created", "autonomous_database_provisioned", "analytics_cloud_instance_started", "object_storage_bucket_created", "block_volume_attached", "file_storage_system_mounted", "archive_storage_used", "data_transfer_service_used", "virtual_cloud_network_created", "security_list_configured", "load_balancer_set_up", "dns_zone_managed", "fast_connect_established"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "oraclecloud" in title or "cloud" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://cloud.oracle.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
