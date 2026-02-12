from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class IbmCloudAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "IBM Cloud"

    @property
    def supported_actions(self) -> List[str]:
        return ["virtual_server_provisioned", "cloud_function_action_created", "openshift_cluster_deployed", "bare_metal_server_reserved", "power_systems_virtual_server_created", "cloud_object_storage_bucket_created", "block_storage_volume_attached", "file_storage_share_mounted", "mass_migration_service_used", "cloud_backup_configured", "vpc_created", "security_group_rule_added", "load_balancer_as_a_service_deployed", "cdn_implemented", "direct_link_established"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "ibmcloud" in title or "cloud" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://cloud.ibm.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
