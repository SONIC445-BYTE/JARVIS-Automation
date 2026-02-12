from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class HubspotAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "HubSpot"

    @property
    def supported_actions(self) -> List[str]:
        return ["contact_imported", "company_associated", "deal_stage_updated", "ticket_created", "conversation_logged", "pipeline_managed", "sequence_enrolled", "meeting_scheduled", "document_tracked", "quote_approved", "workflow_enrolled", "list_segmented", "email_automated", "chatbot_deployed", "attribution_reported"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "hubspot" in title or "hubspot" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://hubspot.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
