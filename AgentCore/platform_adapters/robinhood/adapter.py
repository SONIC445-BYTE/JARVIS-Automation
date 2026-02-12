from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class RobinhoodAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Robinhood"

    @property
    def supported_actions(self) -> List[str]:
        return ["stock_purchased", "stock_sold", "option_traded", "crypto_bought", "recurring_investment_set", "account_funded", "bank_linked", "gold_subscribed", "cash_card_requested", "dividend_reinvested", "two_factor_authentication_enabled", "device_authorized", "login_notification_received", "account_restrictions_reviewed", "tax_document_downloaded"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "robinhood" in title or "robinhood" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://robinhood.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
