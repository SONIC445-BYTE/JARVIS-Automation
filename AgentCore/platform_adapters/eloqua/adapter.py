from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class EloquaAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Eloqua"

    @property
    def supported_actions(self) -> List[str]:
        return ["campaign_orchestrated", "email_deployed", "form_created", "microsite_built", "program_builder_used", "contact_segmented", "lead_scoring_model_applied", "profiler_used", "web_tracking_verified", "subscription_center_managed", "insight_analyzed", "dashboard_customized", "report_scheduled", "a_b_test_executed", "revenue_analytics_viewed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "eloqua" in title or "oracle" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://oracle.com/eloqua/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
