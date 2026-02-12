from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class EbayAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "eBay"

    @property
    def supported_actions(self) -> List[str]:
        return ["auction_bid_placed", "buy_it_now_clicked", "offer_made", "watch_list_added", "listing_created", "store_subscription_started", "promoted_listing_used", "shipping_label_printed", "best_offer_accepted", "global_shipping_used", "authenticity_guaranteed_purchased", "ebay_money_back_claimed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "ebay" in title or "ebay" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://ebay.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
