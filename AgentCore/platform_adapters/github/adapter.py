from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class GithubAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "GitHub"

    @property
    def supported_actions(self) -> List[str]:
        return ["repository_created", "commit_pushed", "pull_request_opened", "branch_merged", "issue_created", "action_workflow_triggered", "package_published", "page_deployed", "release_published", "security_advisory_addressed", "fork_created", "star_given", "wiki_edited", "discussion_started", "sponsorship_set_up"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "github" in title or "github" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://github.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
