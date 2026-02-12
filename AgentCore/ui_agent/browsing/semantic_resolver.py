"""
Browser Semantic Resolver
=========================
Translates high-level browser intents into specific UI actions.
"""

from typing import Dict, Any, Optional

class BrowserSemanticResolver:
    """
    Resolves browser-specific semantic actions.
    """
    
    @staticmethod
    def resolve(action: str, target: str, ui_context: Any) -> Optional[Dict[str, Any]]:
        """
        Try to resolve an action/target to a semantic browser operation.
        
        Args:
            action: The verb (search, click, open)
            target: The object (first result, images, etc.)
            ui_context: Active UI context
            
        Returns:
            Resolved step dict or None if strictly generic.
        """
        target_lower = target.lower()
        
        # 1. Search Query Handling
        if action == "search" or (action == "type" and ui_context.waiting_for and "query" in ui_context.waiting_for):
            # If waiting for query, typing is a semantic input to the search box
            return {
                "type": "type",
                "target": "search_box",  # Semantic target
                "value": target if action == "search" else target, # 'target' holds the query text for 'search' verb usually
                "selector": "input[name='q'], input[type='search'], textarea[name='q']", # Common search selectors
                "description": f"Typed search query: {target}"
            }

        # 2. "Open Result X"
        if "result" in target_lower:
            # Parse index "first result", "result 3"
            import re
            idx = 0
            if "first" in target_lower: idx = 1
            elif "second" in target_lower: idx = 2
            elif "third" in target_lower: idx = 3
            else:
                match = re.search(r"result\s+(\d+)", target_lower)
                if match: idx = int(match.group(1))
            
            if idx > 0:
                return {
                    "type": "click",
                    "target": f"result_{idx}",
                    "selector": f"(//h3)[{idx}]/..", # Common XPath for search results titles
                    "description": f"Clicked search result #{idx}"
                }

        # 3. "Click Images/Maps/News"
        common_tabs = ["all", "images", "maps", "news", "videos", "shopping"]
        if target_lower in common_tabs:
             return {
                "type": "click",
                "target": f"tab_{target_lower}",
                "selector": f"//a[text()='{target.capitalize()}'] | //div[text()='{target.capitalize()}']", 
                "description": f"Switched to {target.capitalize()} tab"
            }
            
        return None
