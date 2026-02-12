from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class GitlabAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "GitLab"

    @property
    def supported_actions(self) -> List[str]:
        return ["project_initialized", "merge_request_submitted", "pipeline_triggered", "container_image_built", "security_scan_run", "auto_devops_enabled", "kubernetes_cluster_connected", "page_deployed", "release_created", "infrastructure_as_code_managed", "epic_created", "roadmap_planned", "wiki_documented", "snippet_shared", "group_managed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "gitlab" in title or "gitlab" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://gitlab.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
