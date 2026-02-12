from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class PinterestAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Pinterest"

    @property
    def supported_actions(self) -> List[str]:
        return ["pin_created", "board_created", "pin_saved", "pin_tried", "section_added", "shopping_list_created", "idea_pin_created", "tag_followed", "visual_search_used", "shop_tab_visited", "merchant_followed", "try_on_feature_used"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "pinterest" in title or "pinterest" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://pinterest.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
