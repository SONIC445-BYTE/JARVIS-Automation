"""
UI Inspector - Extract and Map UI Elements
============================================
Returns UI tree with element properties for targeting.

Sprint 2: Autonomous Action
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class UIElement:
    """Single UI element in the tree."""
    element_id: str
    text: str = ""
    description: str = ""
    class_name: str = ""
    bounds: Dict = field(default_factory=lambda: {"x": 0, "y": 0, "width": 0, "height": 0})
    visible: bool = True
    enabled: bool = True
    focusable: bool = False
    clickable: bool = False
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def center(self) -> tuple:
        """Get center point of element."""
        return (
            self.bounds["x"] + self.bounds["width"] // 2,
            self.bounds["y"] + self.bounds["height"] // 2
        )


@dataclass 
class UITree:
    """Complete UI tree snapshot."""
    timestamp: float
    window_title: str
    window_handle: Any
    root_id: str
    elements: Dict[str, UIElement] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "window_title": self.window_title,
            "root_id": self.root_id,
            "element_count": len(self.elements),
            "elements": {k: v.to_dict() for k, v in self.elements.items()}
        }
    
    def find_by_text(self, text: str, fuzzy: bool = True) -> List[UIElement]:
        """Find elements containing text."""
        results = []
        text_lower = text.lower()
        
        for elem in self.elements.values():
            elem_text = (elem.text or "").lower()
            elem_desc = (elem.description or "").lower()
            
            if fuzzy:
                if text_lower in elem_text or text_lower in elem_desc:
                    results.append(elem)
            else:
                if text_lower == elem_text or text_lower == elem_desc:
                    results.append(elem)
        
        return results
    
    def find_clickable(self) -> List[UIElement]:
        """Find all clickable elements."""
        return [e for e in self.elements.values() if e.clickable and e.visible]


class UIInspector:
    """
    Inspects current UI state and builds element tree.
    
    Uses pywinauto as primary, pyautogui for fallback.
    """
    
    def __init__(self):
        self._element_counter = 0
        self._pywinauto_available = False
        self._init_backends()
    
    def _init_backends(self):
        """Initialize UI automation backends."""
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend="uia")
            self._pywinauto_available = True
            print("[UIInspector] pywinauto UIA backend ready")
        except ImportError:
            print("[UIInspector] pywinauto not available, using fallback")
        except Exception as e:
            print(f"[UIInspector] Backend init error: {e}")
    
    def get_active_window_tree(self) -> Optional[UITree]:
        """Get UI tree for currently active window."""
        if self._pywinauto_available:
            return self._get_tree_pywinauto()
        else:
            return self._get_tree_fallback()
            
    def get_current_state(self) -> Dict:
        """Get flattened UI state for ODAV loop."""
        tree = self.get_active_window_tree()
        if not tree:
            return {"active_window": "unknown", "elements": []}
            
        # Convert tree to flat list of elements for planner
        elements = []
        for elem in tree.elements.values():
            if elem.visible:
                elements.append(elem.to_dict())
                
        return {
            "active_window": tree.window_title,
            "elements": elements,
            "timestamp": tree.timestamp
        }
    
    def get_window_tree(self, title: str) -> Optional[UITree]:
        """Get UI tree for window by title."""
        if self._pywinauto_available:
            return self._get_tree_by_title_pywinauto(title)
        return None
    
    def _get_tree_pywinauto(self) -> Optional[UITree]:
        """Get tree using pywinauto."""
        try:
            from pywinauto import Desktop
            
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            
            if not windows:
                return None
            
            # Get foreground window
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            
            for win in windows:
                if win.handle == hwnd:
                    return self._build_tree_from_window(win)
            
            # Fallback to first window
            return self._build_tree_from_window(windows[0])
            
        except Exception as e:
            print(f"[UIInspector] Error: {e}")
            return None
    
    def _get_tree_by_title_pywinauto(self, title: str) -> Optional[UITree]:
        """Get tree for specific window by title."""
        try:
            from pywinauto import Desktop
            
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            
            for win in windows:
                try:
                    if title.lower() in win.window_text().lower():
                        return self._build_tree_from_window(win)
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"[UIInspector] Error finding window: {e}")
            return None
    
    def _build_tree_from_window(self, window) -> UITree:
        """Build UITree from pywinauto window."""
        self._element_counter = 0
        
        tree = UITree(
            timestamp=time.time(),
            window_title=window.window_text(),
            window_handle=window.handle,
            root_id="root_0"
        )
        
        # Add root
        root_elem = self._wrapper_to_element(window, "root_0", None)
        tree.elements["root_0"] = root_elem
        
        # Recursively add children (limit depth to avoid performance issues)
        self._add_children(window, "root_0", tree, max_depth=5)
        
        return tree
    
    def _add_children(self, wrapper, parent_id: str, tree: UITree, depth: int = 0, max_depth: int = 5):
        """Recursively add child elements."""
        if depth >= max_depth:
            return
        
        try:
            children = wrapper.children()
            
            for child in children[:50]:  # Limit children per level
                self._element_counter += 1
                elem_id = f"elem_{self._element_counter}"
                
                elem = self._wrapper_to_element(child, elem_id, parent_id)
                tree.elements[elem_id] = elem
                tree.elements[parent_id].children.append(elem_id)
                
                # Recurse
                self._add_children(child, elem_id, tree, depth + 1, max_depth)
                
        except Exception:
            pass
    
    def _wrapper_to_element(self, wrapper, elem_id: str, parent_id: Optional[str]) -> UIElement:
        """Convert pywinauto wrapper to UIElement."""
        try:
            rect = wrapper.rectangle()
            bounds = {
                "x": rect.left,
                "y": rect.top,
                "width": rect.width(),
                "height": rect.height()
            }
        except:
            bounds = {"x": 0, "y": 0, "width": 0, "height": 0}
        
        try:
            text = wrapper.window_text()
        except:
            text = ""
        
        try:
            class_name = wrapper.class_name()
        except:
            class_name = ""
        
        try:
            visible = wrapper.is_visible()
        except:
            visible = True
        
        try:
            enabled = wrapper.is_enabled()
        except:
            enabled = True
        
        return UIElement(
            element_id=elem_id,
            text=text,
            class_name=class_name,
            bounds=bounds,
            visible=visible,
            enabled=enabled,
            clickable=class_name in ["Button", "MenuItem", "Link", "CheckBox", "RadioButton"],
            parent_id=parent_id
        )
    
    def _get_tree_fallback(self) -> Optional[UITree]:
        """Fallback using pyautogui for basic info."""
        try:
            import pyautogui
            
            # Get active window info
            active_win = pyautogui.getActiveWindow()
            
            if not active_win:
                return None
            
            tree = UITree(
                timestamp=time.time(),
                window_title=active_win.title,
                window_handle=None,
                root_id="root_0"
            )
            
            tree.elements["root_0"] = UIElement(
                element_id="root_0",
                text=active_win.title,
                bounds={
                    "x": active_win.left,
                    "y": active_win.top,
                    "width": active_win.width,
                    "height": active_win.height
                }
            )
            
            return tree
            
        except Exception as e:
            print(f"[UIInspector] Fallback error: {e}")
            return None


def test_ui_inspector():
    """Test UI inspection."""
    inspector = UIInspector()
    
    print("UI Inspector Test")
    print("=" * 50)
    
    tree = inspector.get_active_window_tree()
    
    if tree:
        print(f"Window: {tree.window_title}")
        print(f"Elements: {len(tree.elements)}")
        print(f"Clickable: {len(tree.find_clickable())}")
        
        # Show first few elements
        for i, (elem_id, elem) in enumerate(tree.elements.items()):
            if i >= 10:
                print("  ...")
                break
            print(f"  {elem_id}: '{elem.text[:30]}' ({elem.class_name})")
    else:
        print("No active window found")


if __name__ == "__main__":
    test_ui_inspector()
