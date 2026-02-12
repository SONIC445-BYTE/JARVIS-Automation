from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class KlaviyoAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Klaviyo"

    @property
    def supported_actions(self) -> List[str]:
        return ["flow_created", "campaign_scheduled", "segment_built", "template_edited", "signup_form_published", "profile_enriched", "list_cleaned", "predictive_analytics_viewed", "back_in_stock_flow_triggered", "price_drop_alert_sent", "benchmark_report_viewed", "cohort_analysis_run", "ltv_calculated", "churn_risk_identified", "a_b_test_analyzed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "klaviyo" in title or "klaviyo" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://klaviyo.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
