from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BitbucketAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Bitbucket"

    @property
    def supported_actions(self) -> List[str]:
        return ["repository_created", "pull_request_created", "pipeline_executed", "deployment_triggered", "branch_permission_set", "bitbucket_pipelines_enabled", "deployment_environment_configured", "jira_issue_linked", "slack_notification_set", "merge_check_configured", "team_invited", "access_control_managed", "fork_synced", "wiki_enabled", "smart_mirror_configured"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "bitbucket" in title or "bitbucket" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://bitbucket.org/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
