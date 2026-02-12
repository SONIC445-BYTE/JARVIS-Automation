from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AlibabaCloudAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Alibaba Cloud"

    @property
    def supported_actions(self) -> List[str]:
        return ["ecs_instance_created", "function_compute_service_deployed", "container_service_kubernetes_cluster_created", "batch_compute_job_submitted", "elastic_gpu_service_activated", "oss_bucket_created", "nas_file_system_mounted", "ebs_block_storage_attached", "archive_storage_used", "data_transport_solution_used", "vpc_established", "security_group_rule_configured", "server_load_balancer_deployed", "cdn_domain_added", "express_connect_established"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "alibabacloud" in title or "alibabacloud" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://alibabacloud.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
