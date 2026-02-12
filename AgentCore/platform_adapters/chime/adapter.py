from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class ChimeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Chime"

    @property
    def supported_actions(self) -> List[str]:
        return ["direct_deposit_received", "spot_me_used", "credit_builder_secured", "savings_rounded_up", "check_deposited", "account_opened", "debit_card_activated", "credit_builder_card_requested", "atm_located", "friend_referred", "transaction_alert_enabled", "card_locked", "two_factor_authentication_set", "account_settings_updated", "support_contacted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "chime" in title or "chime" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://chime.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
