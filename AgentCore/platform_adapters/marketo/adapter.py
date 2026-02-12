from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class MarketoAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Marketo"

    @property
    def supported_actions(self) -> List[str]:
        return ["program_created", "smart_campaign_executed", "email_asset_approved", "landing_page_tested", "nurture_stream_activated", "lead_scored", "segment_smart_list_created", "form_filled", "munchkin_tracking_verified", "rce_report_viewed", "revenue_cycle_modeler_used", "success_path_analyzer_viewed", "email_insights_analyzed", "web_personalization_enabled", "account_profiling_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "marketo" in title or "marketo" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://marketo.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
