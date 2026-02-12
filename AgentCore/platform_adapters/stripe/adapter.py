from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class StripeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Stripe"

    @property
    def supported_actions(self) -> List[str]:
        return ["charge_created", "customer_created", "subscription_started", "invoice_paid", "refund_issued", "account_onboarded", "api_key_generated", "webhook_configured", "connect_account_created", "radar_rule_set", "dispute_managed", "pci_compliance_verified", "two_factor_authentication_enabled", "team_member_invited", "api_version_updated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "stripe" in title or "stripe" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://stripe.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
