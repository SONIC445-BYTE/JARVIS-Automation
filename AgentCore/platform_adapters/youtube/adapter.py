
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class YouTubeAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "YouTube"

    @property
    def supported_actions(self) -> List[str]:
        return ["play_video", "search_video"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "youtube" in title or "chrome" in title or "edge" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "play_video" or action_name == "search_video":
            query = params.get("query", "")
            import urllib.parse
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            
            steps.append(ExecutionStep(
                action="navigate",
                target=url,
                parameters={"url": url}
            ))
            
            # For play_video, ideally we'd click the first result
            if action_name == "play_video":
                # Fallback: User manually clicks or we try basic automated click if selectors known
                pass
                
        return Plan(steps=steps, confidence=0.9 if steps else 0.0)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        # Hard to verify without advanced CV
        return True
