from .base_adapter import BasePlatformAdapter
from ..adapter_registry import registry
from typing import List, Dict, Any

class FileExplorerAdapter(BasePlatformAdapter):
    platform = "explorer"
    supported_actions = ["navigate_to", "select_file", "create_folder", "click", "select_sidebar_item"]

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        if action == "click":
             # Only handle click if we are the ACTIVE app
             if context.get("active_app") == "explorer":
                 return True
             # Or if target is explicitly file-system related (heuristic)
             target = getattr(intent, 'target', intent.get('target') if isinstance(intent, dict) else '')
             if "desktop" in target.lower() or "folder" in target.lower():
                 return True
             return False
        return action in self.supported_actions

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        target = getattr(intent, 'target', intent.get('target') if isinstance(intent, dict) else '')
        
        if action == "navigate_to":
            path = intent.get("path", "C:\\") if isinstance(intent, dict) else getattr(intent, "path", "C:\\")
            return [
                {"type": "hotkey", "target": "win+e", "app": "explorer"},
                {"type": "wait", "target": "1", "app": "explorer"},
                {"type": "click", "target": "toolbar > edit[text~='Address']", "app": "explorer"},
                {"type": "type", "target": "edit[text~='Address']", "value": path, "app": "explorer"},
                {"type": "hotkey", "target": "enter", "app": "explorer"}
            ]
            
        if action == "click" or action == "select_sidebar_item":
            if "desktop" in target.lower():
                # Map 'Click Desktop' to navigation
                return self.build_plan({"action": "navigate_to", "path": "Desktop"}, context)
            
            # Default click
            return [{"type": "click", "target": target, "app": "explorer"}]
            
        return []

    @property
    def capabilities(self) -> Dict[str, List[str]]:
        return {
            "navigate_to": ["native", "ui"],
            "select_file": ["ui"],
            "create_folder": ["native", "ui"],
            "click": ["ui"],
            "select_sidebar_item": ["ui"]
        }

# Register singleton instance
registry.register(FileExplorerAdapter())
