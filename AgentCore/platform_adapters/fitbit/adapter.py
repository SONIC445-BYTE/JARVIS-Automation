from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class FitbitAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Fitbit"

    @property
    def supported_actions(self) -> List[str]:
        return ["activity_tracked", "sleep_logged", "food_logged", "water_logged", "weight_logged", "exercise_auto_recognized", "heart_rate_variability_measured", "spo2_monitored", "skin_temperature_tracked", "stress_management_score_calculated", "premium_trial_started", "health_metrics_dashboard_viewed", "wellness_report_generated", "coach_guidance_received", "family_account_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "fitbit" in title or "fitbit" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://fitbit.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
