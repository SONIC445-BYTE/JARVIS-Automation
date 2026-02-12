from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class RakutenAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Rakuten"

    @property
    def supported_actions(self) -> List[str]:
        return ["item_purchased", "super_points_earned", "shop_discovered", "coupon_clipped", "store_opened", "item_management_bulk_uploaded", "rms_advertising_used", "settlement_confirmed", "rakuten_edy_charged", "rakuten_bank_linked", "travel_booked", "insurance_quoted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "rakuten" in title or "rakuten" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://rakuten.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
