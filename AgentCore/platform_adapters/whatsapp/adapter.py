
from typing import Dict, List, Any
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep

class WhatsAppAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "WhatsApp"

    @property
    def supported_actions(self) -> List[str]:
        return ["send_message", "attach_photo"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "whatsapp" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        
        if action_name == "send_message":
            msg = params.get("message", "")
            steps.append(ExecutionStep(action="type", target=msg, parameters={"text": msg}))
            steps.append(ExecutionStep(action="click", target="send_button", parameters={"x": 0, "y": 0})) # Needs precise coords
            
        elif action_name == "attach_photo":
            # Stub for attachment flow
            steps.append(ExecutionStep(action="click", target="clip_icon", parameters={}))
            steps.append(ExecutionStep(action="click", target="gallery_icon", parameters={}))
            
        return Plan(steps=steps, confidence=0.5) # Low confidence due to hardcoded coords check

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
