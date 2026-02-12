
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class SpotifyAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Spotify"

    @property
    def supported_actions(self) -> List[str]:
        return ["play_music", "search_music"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "spotify" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        if action_name == "play_music" or action_name == "search_music":
            query = params.get("query", "")
            import urllib.parse
            url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
            
            steps.append(ExecutionStep(
                action="navigate",
                target=url,
                parameters={"url": url}
            ))
            
            if action_name == "play_music":
                # Wait and click "Play" on first result
                steps.append(ExecutionStep(action="wait", target="2s", parameters={"seconds": 2}))
                # steps.append(ExecutionStep(action="click", target="Play Button", ...))
                
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
