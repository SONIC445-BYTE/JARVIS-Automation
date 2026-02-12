
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class Plan:
    steps: List[Any]
    confidence: float

class BaseAdapter(ABC):
    """Base class for all platform adapters."""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass
        
    @property
    @abstractmethod
    def supported_actions(self) -> List[str]:
        """List of canonical actions supported (e.g., 'attach_photo', 'send_message')."""
        pass
        
    @abstractmethod
    def detect_ui(self, ui_tree: Dict) -> bool:
        """Return True if this platform is currently active/visible."""
        pass
        
    @abstractmethod
    def build_plan(self, action_name: str, params: Dict) -> Plan:
        """Convert a high-level action to low-level execution plan."""
        pass
        
    @abstractmethod
    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        """Verify if action succeeded based on UI state."""
        pass
