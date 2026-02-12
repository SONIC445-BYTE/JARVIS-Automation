from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PaypalAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "PayPal"

    @property
    def supported_actions(self) -> List[str]:
        return ["payment_sent", "payment_received", "invoice_created", "subscription_managed", "money_pooled", "account_verified", "bank_linked", "card_added", "balance_managed", "currency_converted", "two_factor_authentication_enabled", "security_questions_set", "device_trusted", "login_alert_reviewed", "dispute_filed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "paypal" in title or "paypal" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://paypal.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
