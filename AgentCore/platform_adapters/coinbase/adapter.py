from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class CoinbaseAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Coinbase"

    @property
    def supported_actions(self) -> List[str]:
        return ["crypto_bought", "crypto_sold", "crypto_sent", "crypto_received", "staking_rewards_earned", "wallet_created", "vault_set_up", "recurring_buy_scheduled", "direct_deposit_enabled", "coinbase_card_used", "two_step_verification_enabled", "address_whitelisted", "api_key_restricted", "insurance_policy_viewed", "security_prompt_completed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "coinbase" in title or "coinbase" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://coinbase.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
