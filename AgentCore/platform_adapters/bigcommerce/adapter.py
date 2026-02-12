from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BigcommerceAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "BigCommerce"

    @property
    def supported_actions(self) -> List[str]:
        return ["cart_viewed", "checkout_initiated", "payment_info_added", "shipping_method_selected", "order_reviewed", "purchase_completed", "account_created", "guest_checkout_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "bigcommerce" in title or "bigcommerce" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://bigcommerce.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
