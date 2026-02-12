from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class MyfitnesspalAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "MyFitnessPal"

    @property
    def supported_actions(self) -> List[str]:
        return ["meal_logged", "exercise_recorded", "water_tracked", "weight_entered", "goal_set", "barcode_scanned", "recipe_imported", "nutrition_analyzed", "streak_maintained", "progress_photo_uploaded", "community_posted", "friend_challenged", "premium_subscribed", "report_generated", "coach_consulted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "myfitnesspal" in title or "myfitnesspal" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://myfitnesspal.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
