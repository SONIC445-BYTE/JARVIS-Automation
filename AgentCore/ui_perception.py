"""
UI Perception Layer - pywinauto First, pyautogui Fallback
===========================================================
Observes current screen state and builds UI tree.

ODAV Role: "Observe" layer - perceives the environment.

Priority Order:
1. pywinauto (element-based, semantic, verifiable)
2. pyautogui (coordinate-based, fallback only)

Golden Rule: Never execute a click you cannot explain.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pyautogui


# Try to import pywinauto (Windows-specific)
try:
    from pywinauto import Desktop, Application
    from pywinauto.findwindows import find_windows, ElementNotFoundError
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    print("WARNING: pywinauto not available. UI perception will be limited.")


@dataclass
class UIElement:
    """Represents a detected UI element."""
    element_id: str
    element_type: str  # button, text, edit, listitem, etc.
    name: str
    text: str
    bounds: Tuple[int, int, int, int]  # left, top, right, bottom
    center: Tuple[int, int]
    clickable: bool
    enabled: bool
    visible: bool
    confidence: float = 1.0  # 0.0 to 1.0
    source: str = "accessibility"  # accessibility, ocr, heuristic
    depth: int = 0
    parent_id: Optional[str] = None
    children_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class UISnapshot:
    """Complete snapshot of current UI state."""
    timestamp: str
    active_window: str
    active_window_bounds: Tuple[int, int, int, int]
    screen_size: Tuple[int, int]
    elements: List[UIElement]
    element_count: int
    perception_method: str  # "pywinauto" or "pyautogui_fallback"
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['elements'] = [e.to_dict() for e in self.elements]
        return result


class UIScanner:
    """
    Perceives current screen state using pywinauto (primary) or pyautogui (fallback).
    
    Every scan answers: "What do I observe?"
    """
    
    def __init__(self):
        self.last_snapshot: Optional[UISnapshot] = None
        self.element_counter = 0
        
    def scan(self, max_depth: int = 3) -> UISnapshot:
        """
        Scan current screen and build UI tree.
        
        Args:
            max_depth: Maximum depth to traverse in UI tree
            
        Returns:
            UISnapshot with all detected elements
        """
        from datetime import datetime
        
        screen_size = pyautogui.size()
        
        if PYWINAUTO_AVAILABLE:
            try:
                snapshot = self._scan_with_pywinauto(max_depth)
                snapshot.screen_size = screen_size
                self.last_snapshot = snapshot
                return snapshot
            except Exception as e:
                print(f"DEBUG UIScanner: pywinauto failed ({e}), falling back to pyautogui")
        
        # Fallback to pyautogui (limited capability)
        snapshot = self._scan_with_pyautogui()
        snapshot.screen_size = screen_size
        self.last_snapshot = snapshot
        return snapshot
    
    def _scan_with_pywinauto(self, max_depth: int) -> UISnapshot:
        """Scan using pywinauto - element-based, semantic."""
        from datetime import datetime
        
        desktop = Desktop(backend="uia")
        elements: List[UIElement] = []
        
        # Get active window
        try:
            active_windows = desktop.windows()
            if active_windows:
                active_win = active_windows[0]
                active_name = active_win.window_text() or "Unknown"
                active_bounds = active_win.rectangle()
                win_bounds = (active_bounds.left, active_bounds.top, 
                             active_bounds.right, active_bounds.bottom)
                
                # Traverse UI tree
                self._traverse_element(active_win, elements, 0, max_depth)
            else:
                active_name = "No active window"
                win_bounds = (0, 0, 0, 0)
                
        except Exception as e:
            print(f"DEBUG UIScanner: Error getting active window: {e}")
            active_name = "Error"
            win_bounds = (0, 0, 0, 0)
        
        return UISnapshot(
            timestamp=datetime.now().isoformat(),
            active_window=active_name,
            active_window_bounds=win_bounds,
            screen_size=(0, 0),  # Set by caller
            elements=elements,
            element_count=len(elements),
            perception_method="pywinauto"
        )
    
    def _traverse_element(self, element, elements: List[UIElement], 
                         depth: int, max_depth: int, parent_id: Optional[str] = None):
        """Recursively traverse UI tree."""
        if depth > max_depth:
            return
            
        try:
            # Get element properties
            rect = element.rectangle()
            center = element.rectangle().mid_point()
            
            elem = UIElement(
                element_id=f"elem_{self.element_counter}",
                element_type=element.friendly_class_name() or "unknown",
                name=element.window_text() or "",
                text=self._get_element_text(element),
                bounds=(rect.left, rect.top, rect.right, rect.bottom),
                center=(center.x, center.y),
                clickable=self._is_clickable(element),
                enabled=element.is_enabled() if hasattr(element, 'is_enabled') else True,
                visible=element.is_visible() if hasattr(element, 'is_visible') else True,
                confidence=1.0,
                source="accessibility",
                depth=depth,
                parent_id=parent_id,
                children_count=0
            )
            
            self.element_counter += 1
            elements.append(elem)
            current_id = elem.element_id
            
            # Traverse children
            try:
                children = element.children()
                elem.children_count = len(children)
                for child in children[:20]:  # Limit children to prevent explosion
                    self._traverse_element(child, elements, depth + 1, max_depth, current_id)
            except:
                pass
                
        except Exception as e:
            pass  # Skip elements that can't be read
    
    def _get_element_text(self, element) -> str:
        """Extract text from element."""
        try:
            text = element.window_text()
            if not text and hasattr(element, 'texts'):
                texts = element.texts()
                text = texts[0] if texts else ""
            return text or ""
        except:
            return ""
    
    def _is_clickable(self, element) -> bool:
        """Determine if element is clickable."""
        clickable_types = ['Button', 'CheckBox', 'RadioButton', 'MenuItem', 
                          'ListItem', 'TreeItem', 'TabItem', 'Link', 'Hyperlink']
        try:
            class_name = element.friendly_class_name() or ""
            return any(ct.lower() in class_name.lower() for ct in clickable_types)
        except:
            return False
    
    def _scan_with_pyautogui(self) -> UISnapshot:
        """Fallback scan using pyautogui - limited capability."""
        from datetime import datetime
        
        # pyautogui can only give us basic screen info
        # We flag this as degraded perception
        
        try:
            active_win = pyautogui.getActiveWindow()
            if active_win:
                active_name = active_win.title
                win_bounds = (active_win.left, active_win.top, 
                             active_win.left + active_win.width,
                             active_win.top + active_win.height)
            else:
                active_name = "Unknown"
                win_bounds = (0, 0, 0, 0)
        except:
            active_name = "Unknown"
            win_bounds = (0, 0, 0, 0)
        
        print("WARNING: Using pyautogui fallback - limited UI perception")
        
        return UISnapshot(
            timestamp=datetime.now().isoformat(),
            active_window=active_name,
            active_window_bounds=win_bounds,
            screen_size=(0, 0),
            elements=[],  # pyautogui cannot detect elements
            element_count=0,
            perception_method="pyautogui_fallback"
        )
    
    def find_element(self, target: str, ui_snapshot: Optional[UISnapshot] = None) -> Optional[UIElement]:
        """
        Find an element by text/name match.
        
        Args:
            target: Text or name to search for
            ui_snapshot: Snapshot to search in (uses last if None)
            
        Returns:
            Matching UIElement or None
        """
        snapshot = ui_snapshot or self.last_snapshot
        if not snapshot:
            snapshot = self.scan()
            
        target_lower = target.lower()
        
        # Exact match first
        for elem in snapshot.elements:
            if elem.name.lower() == target_lower or elem.text.lower() == target_lower:
                print(f"DEBUG UIScanner: Found exact match for '{target}': {elem.element_id}")
                return elem
        
        # Partial match
        for elem in snapshot.elements:
            if target_lower in elem.name.lower() or target_lower in elem.text.lower():
                print(f"DEBUG UIScanner: Found partial match for '{target}': {elem.element_id}")
                return elem
                
        print(f"DEBUG UIScanner: No match found for '{target}'")
        return None
    
    def find_by_position(self, position: str, ui_snapshot: Optional[UISnapshot] = None) -> Optional[UIElement]:
        """
        Find element by screen position (top-right, bottom-left, etc.).
        
        Args:
            position: Position descriptor
            ui_snapshot: Snapshot to search in
            
        Returns:
            Element at that position or None
        """
        snapshot = ui_snapshot or self.last_snapshot
        if not snapshot or not snapshot.elements:
            return None
            
        clickable = [e for e in snapshot.elements if e.clickable and e.visible]
        if not clickable:
            clickable = snapshot.elements
            
        if not clickable:
            return None
        
        # Sort by position
        if position == "top-right":
            # Minimize y (top), maximize x (right)
            clickable.sort(key=lambda e: (e.center[1], -e.center[0]))
        elif position == "top-left":
            clickable.sort(key=lambda e: (e.center[1], e.center[0]))
        elif position == "bottom-right":
            clickable.sort(key=lambda e: (-e.center[1], -e.center[0]))
        elif position == "bottom-left":
            clickable.sort(key=lambda e: (-e.center[1], e.center[0]))
        elif position == "center":
            # Closest to screen center
            screen_w, screen_h = snapshot.screen_size
            center_x, center_y = screen_w // 2, screen_h // 2
            clickable.sort(key=lambda e: abs(e.center[0] - center_x) + abs(e.center[1] - center_y))
        elif position in ["first", "1st"]:
            pass  # Already in order
        elif position in ["last", "final"]:
            clickable = clickable[::-1]
        
        if clickable:
            print(f"DEBUG UIScanner: Found element at position '{position}': {clickable[0].element_id}")
            return clickable[0]
        return None
    
    def get_active_window(self) -> Tuple[str, Tuple[int, int, int, int]]:
        """Get current active window name and bounds."""
        try:
            if PYWINAUTO_AVAILABLE:
                desktop = Desktop(backend="uia")
                windows = desktop.windows()
                if windows:
                    win = windows[0]
                    rect = win.rectangle()
                    return (win.window_text(), (rect.left, rect.top, rect.right, rect.bottom))
            
            # Fallback
            win = pyautogui.getActiveWindow()
            if win:
                return (win.title, (win.left, win.top, win.left + win.width, win.top + win.height))
        except:
            pass
        return ("Unknown", (0, 0, 0, 0))
