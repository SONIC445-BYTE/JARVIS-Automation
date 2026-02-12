from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class WrikeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Wrike"

    @property
    def supported_actions(self) -> List[str]:
        return ["task_created", "custom_workflow_applied", "time_tracked", "request_form_submitted", "proof_approved", "project_space_created", "blueprint_used", "report_built", "resource_management_viewed", "calendar_synced", "user_invited", "at_mention_used", "approval_workflow_initiated", "share_link_generated", "mobile_app_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "wrike" in title or "wrike" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://wrike.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
