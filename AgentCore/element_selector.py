"""
Element Selector - DSL for Finding UI Elements
================================================
Flexible selector language for targeting elements.

Sprint 2: Autonomous Action
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, fields
import re


@dataclass
class Selector:
    """Element selector specification."""
    label: Optional[str] = None           # Text/description contains
    class_name: Optional[str] = None      # Element class
    position: Optional[str] = None        # top-left, top-right, center, etc.
    nth: int = 1                          # Which match (1-indexed)
    parent_label: Optional[str] = None    # Parent element text
    fuzzy: bool = True                    # Allow partial matches
    visible_only: bool = True             # Only visible elements
    clickable_only: bool = False          # Only clickable elements
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Selector':
        field_names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in field_names})


class ElementSelector:
    """
    Resolves selectors to UI elements.
    
    Selector DSL:
    - label: Match by text content
    - class_name: Match by element class
    - position: Match by screen position (top-left, center, etc.)
    - nth: Select Nth match
    - parent_label: Element must have parent with this text
    """
    
    # Position regions (as fractions of screen/container)
    POSITIONS = {
        "top-left": (0, 0.33, 0, 0.33),
        "top": (0.33, 0.66, 0, 0.33),
        "top-right": (0.66, 1, 0, 0.33),
        "left": (0, 0.33, 0.33, 0.66),
        "center": (0.33, 0.66, 0.33, 0.66),
        "right": (0.66, 1, 0.33, 0.66),
        "bottom-left": (0, 0.33, 0.66, 1),
        "bottom": (0.33, 0.66, 0.66, 1),
        "bottom-right": (0.66, 1, 0.66, 1),
    }
    
    def resolve(self, selector: Selector, ui_tree) -> List:
        """
        Resolve selector to matching elements.
        
        Args:
            selector: Selector specification
            ui_tree: UITree from UIInspector
            
        Returns:
            List of matching UIElements
        """
        if not ui_tree or not ui_tree.elements:
            return []
        
        candidates = list(ui_tree.elements.values())
        
        # Filter by visibility
        if selector.visible_only:
            candidates = [e for e in candidates if e.visible]
        
        # Filter by clickable
        if selector.clickable_only:
            candidates = [e for e in candidates if e.clickable]
        
        # Filter by label/text
        if selector.label:
            candidates = self._filter_by_label(candidates, selector.label, selector.fuzzy)
        
        # Filter by class name
        if selector.class_name:
            candidates = self._filter_by_class(candidates, selector.class_name)
        
        # Filter by position
        if selector.position and candidates:
            candidates = self._filter_by_position(candidates, selector.position, ui_tree)
        
        # Filter by parent
        if selector.parent_label and candidates:
            candidates = self._filter_by_parent(candidates, selector.parent_label, ui_tree)
        
        # Apply nth selector
        if candidates and selector.nth > 0:
            if selector.nth <= len(candidates):
                return [candidates[selector.nth - 1]]
            return []
        
        return candidates
    
    def _filter_by_label(self, elements: List, label: str, fuzzy: bool) -> List:
        """Filter elements by text label."""
        label_lower = label.lower()
        matches = []
        
        for elem in elements:
            text = (elem.text or "").lower()
            desc = (elem.description or "").lower()
            
            if fuzzy:
                if label_lower in text or label_lower in desc:
                    matches.append(elem)
            else:
                if label_lower == text or label_lower == desc:
                    matches.append(elem)
        
        return matches
    
    def _filter_by_class(self, elements: List, class_name: str) -> List:
        """Filter elements by class name."""
        class_lower = class_name.lower()
        return [e for e in elements if class_lower in (e.class_name or "").lower()]
    
    def _filter_by_position(self, elements: List, position: str, ui_tree) -> List:
        """Filter elements by screen position."""
        if position not in self.POSITIONS:
            return elements
        
        x_min_frac, x_max_frac, y_min_frac, y_max_frac = self.POSITIONS[position]
        
        # Get container bounds (root element or screen)
        root = ui_tree.elements.get(ui_tree.root_id)
        if not root:
            return elements
        
        container_w = root.bounds.get("width", 1920)
        container_h = root.bounds.get("height", 1080)
        container_x = root.bounds.get("x", 0)
        container_y = root.bounds.get("y", 0)
        
        x_min = container_x + container_w * x_min_frac
        x_max = container_x + container_w * x_max_frac
        y_min = container_y + container_h * y_min_frac
        y_max = container_y + container_h * y_max_frac
        
        matches = []
        for elem in elements:
            cx, cy = elem.center
            if x_min <= cx <= x_max and y_min <= cy <= y_max:
                matches.append(elem)
        
        return matches
    
    def _filter_by_parent(self, elements: List, parent_label: str, ui_tree) -> List:
        """Filter elements by parent text."""
        parent_lower = parent_label.lower()
        matches = []
        
        for elem in elements:
            parent_id = elem.parent_id
            while parent_id:
                parent = ui_tree.elements.get(parent_id)
                if not parent:
                    break
                
                if parent_lower in (parent.text or "").lower():
                    matches.append(elem)
                    break
                
                parent_id = parent.parent_id
        
        return matches
    
    def parse_selector_string(self, selector_str: str) -> Selector:
        """
        Parse human-readable selector string.
        
        Examples:
            "Submit button"
            "text field in Login form"
            "first link at top-right"
        """
        selector = Selector()
        selector_str = selector_str.lower().strip()
        
        # Check for position
        for pos_name in self.POSITIONS.keys():
            if pos_name in selector_str:
                selector.position = pos_name
                selector_str = selector_str.replace(pos_name, "").strip()
                break
        
        # Check for nth
        nth_match = re.search(r"\b(first|second|third|1st|2nd|3rd|\d+)\b", selector_str)
        if nth_match:
            nth_word = nth_match.group(1)
            nth_map = {"first": 1, "second": 2, "third": 3, "1st": 1, "2nd": 2, "3rd": 3}
            selector.nth = nth_map.get(nth_word, int(nth_word) if nth_word.isdigit() else 1)
            selector_str = selector_str[:nth_match.start()] + selector_str[nth_match.end():]
        
        # Check for "in <parent>"
        in_match = re.search(r"\bin\s+(.+)$", selector_str)
        if in_match:
            selector.parent_label = in_match.group(1).strip()
            selector_str = selector_str[:in_match.start()].strip()
        
        # Check for class hints
        class_hints = {
            "button": "Button",
            "link": "Link",
            "checkbox": "CheckBox",
            "text field": "Edit",
            "input": "Edit",
            "dropdown": "ComboBox",
            "menu": "MenuItem",
        }
        for hint, class_name in class_hints.items():
            if hint in selector_str:
                selector.class_name = class_name
                selector_str = selector_str.replace(hint, "").strip()
                break
        
        # Remaining text is the label
        selector.label = selector_str.strip() or None
        
        return selector


def test_element_selector():
    """Test element selector."""
    es = ElementSelector()
    
    tests = [
        "Submit button",
        "first link at top-right",
        "text field in Login form",
        "Save button in Settings",
        "second checkbox",
    ]
    
    print("Element Selector Test")
    print("=" * 50)
    
    for s in tests:
        selector = es.parse_selector_string(s)
        print(f"\nInput: '{s}'")
        print(f"  label: {selector.label}")
        print(f"  class: {selector.class_name}")
        print(f"  position: {selector.position}")
        print(f"  nth: {selector.nth}")
        print(f"  parent: {selector.parent_label}")


if __name__ == "__main__":
    test_element_selector()
