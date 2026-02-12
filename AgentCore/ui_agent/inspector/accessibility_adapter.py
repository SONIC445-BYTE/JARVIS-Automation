import pywinauto
from pywinauto import Desktop
from typing import List, Optional, Dict, Any
from .element_model import ElementModel

class AccessibilityAdapter:
    """Adapter for Windows UI Automation using pywinauto."""
    
    def __init__(self):
        self.desktop = Desktop(backend="uia")
    
    def list_windows(self) -> List[Dict[str, Any]]:
        """List all top-level windows."""
        windows = []
        for win in self.desktop.windows():
            try:
                windows.append({
                    "title": win.window_text(),
                    "class_name": win.class_name(),
                    "handle": win.handle,
                    "process_id": win.process_id()
                })
            except Exception:
                continue
        return windows

    def get_tree(self, window_handle: int) -> Optional[ElementModel]:
        """Get the full accessibility tree for a window."""
        try:
            win = self.desktop.window(handle=window_handle)
            return self._serialize_element(win)
        except Exception as e:
            print(f"[Accessibility] Error getting tree for {window_handle}: {e}")
            return None

    def _serialize_element(self, element, parent_id=None) -> ElementModel:
        """Recursively serialize a pywinauto element to ElementModel."""
        # This is a simplified version; real implementation would be more robust
        rect = element.rectangle()
        model = ElementModel(
            id=str(element.handle) if hasattr(element, 'handle') else str(id(element)),
            role=element.control_type(),
            text=element.window_text(),
            rect=(rect.left, rect.top, rect.width(), rect.height()),
            enabled=element.is_enabled(),
            visible=element.is_visible(),
            parent_id=parent_id
        )
        
        # Add children
        for child in element.children():
            child_model = self._serialize_element(child, parent_id=model.id)
            model.children_ids.append(child_model.id)
            
        return model

    def perform_action(self, element_id: str, action: str, value: Any = None):
        """Perform action on an element."""
        # In a real implementation, we'd look up the element by ID
        # For now, this is a placeholder
        print(f"[Accessibility] Performing {action} on {element_id}")
        pass
