from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class NotionAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Notion"

    @property
    def supported_actions(self) -> List[str]:
        return ["page_created", "database_set_up", "block_edited", "template_duplicated", "relation_linked", "workspace_organized", "teamspace_created", "permission_managed", "integration_connected", "api_accessed", "member_invited", "comment_threaded", "mention_used", "page_shared_publicly", "export_generated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "notion" in title or "notion" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://notion.so/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
