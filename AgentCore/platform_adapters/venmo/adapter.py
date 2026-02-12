from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class VenmoAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Venmo"

    @property
    def supported_actions(self) -> List[str]:
        return ["payment_made", "payment_requested", "split_bill_initiated", "qr_code_scanned", "instant_transfer_used", "bank_account_linked", "debit_card_added", "profile_customized", "privacy_setting_adjusted", "direct_deposit_set_up", "pin_code_set", "face_id_enabled", "transaction_alert_received", "card_frozen", "unauthorized_activity_reported"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "venmo" in title or "venmo" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://venmo.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
