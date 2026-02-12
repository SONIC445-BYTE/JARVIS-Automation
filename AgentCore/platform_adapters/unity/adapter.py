from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class UnityAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Unity"

    @property
    def supported_actions(self) -> List[str]:
        return ["project_created", "asset_imported", "scene_built", "game_deployed", "asset_store_purchase_made", "collaborate_feature_used", "plastic_scm_used", "analytics_dashboard_viewed", "unity_plus_subscribed", "unity_pro_purchased", "asset_store_publisher_approved", "certification_exam_taken"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "unity" in title or "unity" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://unity.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
