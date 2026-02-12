from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class EtsyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Etsy"

    @property
    def supported_actions(self) -> List[str]:
        return ["handmade_item_listed", "vintage_item_searched", "custom_request_sent", "favorite_shop_added", "pattern_website_created", "etsy_ads_started", "deposit_scheduled", "shop_policies_updated", "etsy_payments_onboarded", "etsy_shipping_labels_purchased", "etsy_plus_subscribed", "star_seller_achieved"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "etsy" in title or "etsy" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://etsy.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
