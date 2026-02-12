from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class UnrealEngineAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Unreal Engine"

    @property
    def supported_actions(self) -> List[str]:
        return ["project_started", "blueprint_created", "nanite_enabled", "lumen_activated", "marketplace_asset_purchased", "quixel_bridge_used", "metahuman_created", "learning_platform_accessed", "unreal_engine_license_purchased", "fab_marketplace_used", "enterprise_support_contracted"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "unrealengine" in title or "unrealengine" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://unrealengine.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
