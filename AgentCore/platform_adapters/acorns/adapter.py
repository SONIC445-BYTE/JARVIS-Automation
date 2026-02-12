from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class AcornsAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Acorns"

    @property
    def supported_actions(self) -> List[str]:
        return ["round_up_invested", "recurring_investment_set", "found_money_earned", "later_account_opened", "early_account_managed", "portfolio_selected", "aggressive_conservative_slider_adjusted", "gift_card_purchased", "referral_bonus_earned", "financial_literacy_content_consumed", "market_explained_read", "grow_magazine_article_viewed", "money_lesson_completed", "news_updated_checked", "support_ticket_submitted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "acorns" in title or "acorns" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://acorns.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
