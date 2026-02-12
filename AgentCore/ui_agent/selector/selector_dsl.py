import re
from typing import List, Dict, Any, Optional
from ..inspector.element_model import ElementModel
from .fuzzy_matcher import FuzzyMatcher

class SelectorDSL:
    """
    Resolves human-readable selector strings into UI elements.
    Example: app=WhatsApp > window=WhatsApp > button[text~="Attach"]
    """
    
    def __init__(self, accessibility_adapter, browser_adapter):
        self.acc_adapter = accessibility_adapter
        self.browser_adapter = browser_adapter
        self.fuzzy_matcher = FuzzyMatcher()

    def resolve(self, selector_str: str, context_win_handle: Optional[int] = None) -> List[ElementModel]:
        """Parse and resolve a selector string."""
        print(f"[SelectorDSL] Resolving: {selector_str}")
        
        # Split by '>' for hierarchy
        parts = [p.strip() for p in selector_str.split(">")]
        
        current_elements = []
        if context_win_handle:
            # Start from window tree
            root = self.acc_adapter.get_tree(context_win_handle)
            if root:
                current_elements = [root]
        else:
            # Start from all top-level windows
            windows = self.acc_adapter.list_windows()
            # This is a bit simplified; real logic would map window metadata to ElementModels
            pass

        for part in parts:
            # Parse part: role=value or role[attr=val] or role[attr~=val]
            current_elements = self._filter_elements(current_elements, part)
            if not current_elements:
                break
                
        return current_elements

    def _filter_elements(self, elements: List[ElementModel], part: str) -> List[ElementModel]:
        """Filter current elements based on the selector part."""
        # Simple regex for role=value or role[attr=val]
        match = re.match(r'(\w+)(?:\[(\w+)([\=\~]\=)"(.+)"\])?', part)
        if not match:
            # Check for simple role=value
            kv_match = re.match(r'(\w+)=(.+)', part)
            if kv_match:
                role, value = kv_match.groups()
                return [e for e in self._get_all_descendants(elements) if e.role.lower() == role.lower() and value.lower() in e.text.lower()]
            return []

        role, attr, op, val = match.groups()
        filtered = []
        
        candidates = self._get_all_descendants(elements)
        for e in candidates:
            if role and e.role.lower() != role.lower() and role.lower() != "any":
                continue
                
            if attr:
                target_val = getattr(e, attr, e.attributes.get(attr, ""))
                if op == "==":
                    if str(target_val).lower() == val.lower():
                        filtered.append(e)
                elif op == "~=": # Fuzzy match
                    if self.fuzzy_matcher.match(val, str(target_val)):
                        filtered.append(e)
            else:
                filtered.append(e)
                
        return filtered

    def _get_all_descendants(self, elements: List[ElementModel]) -> List[ElementModel]:
        """Flatten tree to get all descendants."""
        all_elements = []
        def traverse(e):
            all_elements.append(e)
            # In real implementation, elements would have direct child links
            # and we'd use those. For now, we assume the tree is pre-flattened
            # or we fetch children via adapter.
            pass
        for e in elements:
            traverse(e)
        return all_elements
