from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class RechargeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Recharge"

    @property
    def supported_actions(self) -> List[str]:
        return ["subscription_created", "billing_cycle_managed", "dunning_email_sent", "plan_upgraded", "plan_downgraded", "churn_prevented", "metered_billing_calculated"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "recharge" in title or "rechargepayments" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://rechargepayments.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
