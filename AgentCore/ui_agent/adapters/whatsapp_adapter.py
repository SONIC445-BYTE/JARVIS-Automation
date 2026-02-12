from .base_adapter import BasePlatformAdapter
from ..adapter_registry import registry
from typing import List, Dict, Any

class WhatsAppAdapter(BasePlatformAdapter):
    platform = "whatsapp"
    supported_actions = ["send_message", "post_status"]

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        return action in self.supported_actions

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        
        if action == "send_message":
            recipient = intent.get("recipient", "someone") if isinstance(intent, dict) else getattr(intent, "recipient", "someone")
            message = intent.get("message", "hello") if isinstance(intent, dict) else getattr(intent, "message", "hello")
            
            return [
                {"type": "focus_app", "target": "WhatsApp", "app": "whatsapp"},
                {"type": "click", "target": f"label[text~='{recipient}']", "app": "whatsapp"},
                {"type": "type", "target": "textbox", "value": message, "app": "whatsapp"},
                {"type": "hotkey", "target": "enter", "app": "whatsapp"}
            ]
        
        elif action == "post_status":
            return [
                {"type": "focus_app", "target": "whatsapp"},
                {"type": "open_status"},
                {"type": "attach_photo", "strategy": "gallery_top_right"},
                {"type": "confirm"}
            ]
            
        return []

    def execute_native(self, intent: Any, context: Dict[str, Any]) -> Any:
        """Demo native execution by calling legacy automation directly."""
        print("[WhatsAppAdapter] Attempting Native Automation (Simulation)")
        # In a real scenario, this would import and call the old selenium/pyautogui wrapper
        # For now, we simulate success for the 'send_message' action if params are correct
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        if action == "send_message":
            return "SUCCESS: Sent via Native API"
        return None

# Register singleton instance
registry.register(WhatsAppAdapter())
