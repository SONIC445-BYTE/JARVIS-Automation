from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class FidelityAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Fidelity"

    @property
    def supported_actions(self) -> List[str]:
        return ["trade_executed", "order_type_selected", "automatic_investment_set", "dividend_reinvestment_enabled", "esg_fund_invested", "portfolio_rebalanced", "retirement_planner_used", "full_view_aggregated", "wealth_management_consulted", "plan_529_managed", "research_report_accessed", "stock_comparison_tool_used", "fixed_income_analysis_viewed", "market_monitor_watched", "learning_center_accessed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "fidelity" in title or "fidelity" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://fidelity.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
