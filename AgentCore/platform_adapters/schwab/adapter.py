from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class SchwabAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Charles Schwab"

    @property
    def supported_actions(self) -> List[str]:
        return ["equity_traded", "fixed_income_purchased", "etf_bought", "margin_loan_utilized", "ipo_access_requested", "portfolio_checkup_completed", "financial_plan_created", "robo_advisor_used", "trust_account_opened", "charitable_giving_account_managed", "market_insight_read", "stock_rating_viewed", "international_research_accessed", "learning_portal_visited", "podcast_listened"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "schwab" in title or "schwab" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://schwab.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
