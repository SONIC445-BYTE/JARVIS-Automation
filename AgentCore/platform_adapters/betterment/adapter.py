from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class BettermentAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Betterment"

    @property
    def supported_actions(self) -> List[str]:
        return ["goal_based_investing_started", "portfolio_deposited", "rebalancing_automated", "tax_coordinated_portfolio_enabled", "crypto_invested", "goal_projected", "advice_accessed", "checking_account_opened", "joint_account_created", "trust_account_established", "educational_article_read", "tool_used", "performance_analyzed", "fee_comparison_made", "customer_support_chatted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "betterment" in title or "betterment" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://betterment.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
