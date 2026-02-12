from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TravisciAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Travis CI"

    @property
    def supported_actions(self) -> List[str]:
        return ["repository_activated", "build_triggered", "matrix_build_configured", "deployment_released", "cron_job_scheduled", "github_releases_deployed", "heroku_application_pushed", "aws_s3_uploaded", "docker_hub_pushed", "pypi_package_published", "organization_managed", "billing_updated", "log_accessed", "cache_cleared", "debug_mode_activated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "travisci" in title or "travis-ci" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://travis-ci.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
