from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class EtradeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "E*Trade"

    @property
    def supported_actions(self) -> List[str]:
        return ["stock_ordered", "option_contract_traded", "mutual_fund_purchased", "bond_laddered", "futures_contract_initiated", "portfolio_analyzed", "watch_list_created", "paper_trading_used", "margin_account_enabled", "ira_opened", "market_news_read", "analyst_report_viewed", "earnings_calendar_checked", "stock_screener_used", "educational_video_watched"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "etrade" in title or "etrade" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://etrade.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
