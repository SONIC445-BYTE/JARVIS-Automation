from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class HeadspaceAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Headspace"

    @property
    def supported_actions(self) -> List[str]:
        return ["meditation_completed", "sleep_cast_played", "focus_music_listened", "course_started", "mindful_moment_taken", "progress_tracked", "streak_extended", "reminder_set", "buddy_added", "session_downloaded", "subscription_gifted", "work_plan_accessed", "family_plan_joined", "sleep_analysis_viewed", "sos_session_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "headspace" in title or "headspace" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://headspace.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
