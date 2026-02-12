"""
Follow-up Guard
===============
Determines if an intent is a UI follow-up and enforces context ownership.
"""

from typing import Dict, Any
from ..context.ui_context import UIContext

class FollowupGuard:
    """
    Guard logic for UI follow-ups.
    """
    
    # Verbs that imply interaction with *current* context
    FOLLOWUP_VERBS = {
        "click", "select", "press", "type", "enter", 
        "scroll", "drag", "drop", "double click", "right click",
        "copy", "paste"
    }
    
    @staticmethod
    def is_followup(intent: Any, ui_context: UIContext) -> bool:
        """
        Check if intent is a follow-up to the current UI session.
        
        Criteria:
        1. UI Context is ACTIVE
        2. Action is a follow-up verb (click, type, etc.)
        3. (Optional) Target exists in current context
        """
        if not ui_context.is_active():
            return False
            
        # Handle intent object or dict
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        
        # Check verb
        # Normalize action (e.g. "click_element" -> "click")
        base_action = action.split('_')[0].lower()
        
        if base_action in FollowupGuard.FOLLOWUP_VERBS:
            print(f"[FollowupGuard] Detected follow-up action: {action}")
            return True
            
        return False
        
    @staticmethod
    def validate_adapter_ownership(intent: Any, ui_context: UIContext, adapter_name: str) -> bool:
        """
        Ensure the adapter attempting this action owns the session.
        """
        if not ui_context.is_active():
            return True # No active session, anyone can claim
            
        return ui_context.validate_ownership(adapter_name)
