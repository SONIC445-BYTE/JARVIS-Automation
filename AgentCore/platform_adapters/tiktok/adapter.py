from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class TiktokAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "TikTok"

    @property
    def supported_actions(self) -> List[str]:
        return ["video_posted", "video_liked", "comment_posted", "sound_used", "duet_created", "stitch_created", "live_streamed", "effect_applied", "collection_saved", "creator_followed", "q_and_a_posted", "series_created"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "tiktok" in title or "tiktok" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://tiktok.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
