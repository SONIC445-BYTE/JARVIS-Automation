from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class RevolutAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Revolut"

    @property
    def supported_actions(self) -> List[str]:
        return ["transfer_made", "card_payment_processed", "vault_created", "crypto_exchanged", "stock_traded", "account_upgraded", "physical_card_ordered", "virtual_card_created", "salary_advanced", "insurance_purchased", "security_feature_enabled", "location_based_security_set", "disposable_virtual_card_used", "pin_changed", "unauthorized_transaction_disputed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "revolut" in title or "revolut" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://revolut.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
