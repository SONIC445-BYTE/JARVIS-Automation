"""
UI Context - Persistent Session State
=======================================
Manages the state of the UI session across multiple user utterances.
Enforces session continuity, adapter ownership, and context expiry.
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class UIContextData:
    """Serializable context data."""
    session_id: str
    created_at: float
    last_action_ts: float
    active: bool
    owning_adapter: Optional[str]
    window_handle: Optional[str]
    window_title: Optional[str]
    last_elements: List[Dict] = field(default_factory=list)
    selector_map: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    waiting_for: List[str] = field(default_factory=list) # e.g. ["query", "click"]
    selector_scope: Dict[str, Any] = field(default_factory=dict) # e.g. {"window_handle": "...", "adapter": "..."}

class UIContext:
    """
    Singleton-like access to the current UI session.
    State persists until expiry or explicit clear.
    """
    _instance = None
    
    # Expiry configuration
    EXPIRY_SECONDS = 60 * 5  # 5 minutes inactivity
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UIContext, cls).__new__(cls)
            cls._instance._reset()
        return cls._instance
    
    def _reset(self):
        """Reset to clean state."""
        self._data = UIContextData(
            session_id=str(uuid.uuid4()),
            created_at=time.time(),
            last_action_ts=time.time(),
            active=False,
            owning_adapter=None,
            window_handle=None,
            window_title=None
        )
        
    def get_session_id(self) -> str:
        """Get current session ID."""
        self._check_expiry()
        return self._data.session_id
        
    def is_active(self) -> bool:
        """Check if UI context is strictly active."""
        self._check_expiry()
        return self._data.active
        
    def set_active(self, active: bool, adapter_name: Optional[str] = None):
        """
        Set active state. 
        Active=True should only be set after a confirmed successful UI action.
        """
        self._data.active = active
        if active:
            self._touch()
            if adapter_name:
                self._data.owning_adapter = adapter_name
                
    def update_snapshot(self, window_title: str, elements: List[Dict], window_handle: str = None):
        """Update the perceived UI state."""
        self._touch()
        self._data.window_title = window_title
        if window_handle:
            self._data.window_handle = window_handle
            
        self._data.last_elements = elements
        
        # Rebuild selector map (simple name/text index)
        self._data.selector_map = {}
        for el in elements:
            # Map ID to element
            self._data.selector_map[el.get('element_id')] = el
            
            # Map text/name to element ID (for fast lookup)
            name = el.get('name', '').lower()
            text = el.get('text', '').lower()
            if name:
                if name not in self._data.selector_map:
                    self._data.selector_map[name] = []
                if isinstance(self._data.selector_map[name], list):
                    self._data.selector_map[name].append(el)
            
            if text and text != name:
                if text not in self._data.selector_map:
                    self._data.selector_map[text] = []
                if isinstance(self._data.selector_map[text], list):
                    self._data.selector_map[text].append(el)
                    
                    self._data.selector_map[text].append(el)

    def set_wait_state(self, expected_actions: List[str]):
        """Set the UI into a wait state expecting specific follow-ups."""
        self._touch()
        self._data.waiting_for = expected_actions
        print(f"[UIContext] Entered WAIT STATE. Expecting: {expected_actions}")

    def clear_wait_state(self):
        """Clear wait state."""
        self._data.waiting_for = []

    def set_scope(self, scope: Dict[str, Any]):
        """Restrict selector resolution to a specific scope."""
        self._touch()
        self._data.selector_scope = scope
        
    def get_elements_by_text(self, text: str) -> List[Dict]:
        """Find elements visible in current context context."""
        self._check_expiry()
        if not self._data.active:
            return []
            
        # Scope Filter (Mock logic for now, real implementation would filter by handle/namespace)
        # if self._data.selector_scope: ...
        
        text = text.lower()
        # Direct lookup (optimistic)
        if text in self._data.selector_map:
            val = self._data.selector_map[text]
            if isinstance(val, list):
                return val
            return [val]
            
        # Scan (fallback)
        results = []
        for el in self._data.last_elements:
            el_name = el.get('name', '').lower()
            el_text = el.get('text', '').lower()
            if text in el_name or text in el_text:
                results.append(el)
        return results

    def validate_ownership(self, adapter_name: str) -> bool:
        """
        Verify if the calling adapter owns the current session.
        Returns True if session is new/inactive OR if owned by adapter.
        """
        self._check_expiry()
        
        if not self._data.active:
            return True
            
        if self._data.owning_adapter == adapter_name:
            return True
            
        print(f"WARNING: Adapter mismatch! Owner: {self._data.owning_adapter}, Caller: {adapter_name}")
        return False
        
    def _touch(self):
        """Update last action timestamp."""
        self._data.last_action_ts = time.time()
        
    def _check_expiry(self):
        """Invalidate session if expired."""
        if time.time() - self._data.last_action_ts > self.EXPIRY_SECONDS:
            if self._data.active:
                print(f"[UIContext] Session {self._data.session_id} expired due to inactivity.")
                self._reset()
