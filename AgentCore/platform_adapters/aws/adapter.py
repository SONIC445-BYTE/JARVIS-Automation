from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AwsAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "AWS"

    @property
    def supported_actions(self) -> List[str]:
        return ["ec2_instance_launched", "lambda_function_deployed", "ecs_task_run", "eks_cluster_created", "batch_job_submitted", "s3_bucket_created", "ebs_volume_attached", "efs_file_system_mounted", "glacier_archive_uploaded", "storage_gateway_configured", "vpc_created", "route_table_configured", "load_balancer_deployed", "cloudfront_distribution_created", "transit_gateway_established"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "aws" in title or "aws" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://aws.amazon.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
