from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class CashappAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Cash App"

    @property
    def supported_actions(self) -> List[str]:
        return ["cash_sent", "cash_received", "bitcoin_purchased", "stock_bought", "direct_deposit_received", "cash_card_activated", "boost_applied", "routing_number_copied", "paper_money_deposited", "tax_refund_deposited", "security_lock_enabled", "notification_preference_set", "pin_changed", "account_closed", "fraud_reported"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "cashapp" in title or "cash" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://cash.app/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
