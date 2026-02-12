from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ShopifyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Shopify"

    @property
    def supported_actions(self) -> List[str]:
        return ["store_created", "product_added", "theme_customized", "order_processed", "app_installed", "payment_gateway_configured", "discount_code_created", "abandoned_cart_recovery_set", "shopify_payments_activated", "shopify_shipping_used", "shopify_capital_accessed", "shopify_email_sent"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "shopify" in title or "shopify" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://shopify.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
