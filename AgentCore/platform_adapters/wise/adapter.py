from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class WiseAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Wise"

    @property
    def supported_actions(self) -> List[str]:
        return ["transfer_initiated", "recipient_added", "rate_alert_set", "wise_card_used", "business_account_opened", "verification_document_uploaded", "bank_details_shared", "jar_created", "direct_debit_set_up", "api_integrated", "two_factor_authentication_enabled", "login_alert_reviewed", "card_frozen", "statement_downloaded", "account_closure_requested"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "wise" in title or "wise" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://wise.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
