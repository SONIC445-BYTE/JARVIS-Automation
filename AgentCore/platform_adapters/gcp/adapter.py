from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class GcpAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Google Cloud Platform"

    @property
    def supported_actions(self) -> List[str]:
        return ["compute_engine_vm_started", "cloud_function_deployed", "gke_cluster_created", "cloud_run_service_deployed", "batch_job_submitted", "cloud_storage_bucket_created", "persistent_disk_attached", "filestore_instance_mounted", "archive_storage_used", "transfer_service_job_run", "vpc_network_created", "firewall_rule_configured", "cloud_load_balancing_set_up", "cloud_cdn_enabled", "cloud_interconnect_established"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "gcp" in title or "cloud" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://cloud.google.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
