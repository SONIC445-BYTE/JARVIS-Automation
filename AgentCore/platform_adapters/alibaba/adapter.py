from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AlibabaAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Alibaba"

    @property
    def supported_actions(self) -> List[str]:
        return ["product_sourced", "inquiry_sent", "trade_assurance_order_placed", "supplier_contacted", "company_profile_created", "product_showcase_uploaded", "rfq_responded", "gold_supplier_subscribed", "taobao_product_imported", "logistics_service_booked", "inspection_service_ordered", "trade_show_registered"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "alibaba" in title or "alibaba" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://alibaba.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
