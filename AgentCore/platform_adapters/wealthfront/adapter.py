from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class WealthfrontAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Wealthfront"

    @property
    def supported_actions(self) -> List[str]:
        return ["account_funded", "portfolio_automated", "auto_deposit_scheduled", "tax_loss_harvesting_enabled", "home_planning_started", "risk_tolerance_assessed", "financial_plan_projected", "plan_529_recommended", "high_yield_cash_account_opened", "line_of_credit_accessed", "investment_explanation_read", "historical_performance_viewed", "methodology_whitepaper_downloaded", "faq_consulted", "support_contacted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "wealthfront" in title or "wealthfront" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://wealthfront.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
