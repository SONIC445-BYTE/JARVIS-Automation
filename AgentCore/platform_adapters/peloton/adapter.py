from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PelotonAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Peloton"

    @property
    def supported_actions(self) -> List[str]:
        return ["class_taken", "milestone_achieved", "high_five_exchanged", "stack_created", "challenge_joined", "output_tracked", "heart_rate_monitored", "personal_record_set", "streak_maintained", "achievement_badge_earned", "membership_paused", "apparel_purchased", "referral_code_used", "scenic_content_ridden", "lanebreak_game_played"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "peloton" in title or "onepeloton" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://onepeloton.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
