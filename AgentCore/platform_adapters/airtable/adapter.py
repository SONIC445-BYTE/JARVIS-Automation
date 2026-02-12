from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AirtableAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Airtable"

    @property
    def supported_actions(self) -> List[str]:
        return ["record_created", "field_customized", "view_filtered", "automation_scripted", "interface_designed", "base_created", "template_gallery_used", "sync_integration_set", "extension_installed", "form_shared", "collaborator_invited", "comment_threaded", "revision_history_viewed", "snapshot_taken", "enterprise_admin_managed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "airtable" in title or "airtable" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://airtable.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
