from typing import List, Dict, Any

class BasePlatformAdapter:
    """
    Standard contract for all J.A.R.V.I.S. platform adapters.
    ALL adapters must inherit from this and register themselves.
    """
    platform: str = "generic"
    supported_actions: List[str] = []

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        """Return True if this adapter can handle the specific intent."""
        # NEW: Context Awareness (Phase 27 Fix)
        active_app = context.get("active_app", "").lower()
        my_platform = self.platform.lower()
        
        # If we are the active app, we claim generic UI actions
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        if active_app and active_app == my_platform:
             if action in ["click", "type", "scroll", "wait"]:
                 return True
                 
        # Default implementation checks against supported_actions
        return action in self.supported_actions

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Produce a list of atomic actions for the executor.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement build_plan")

    def execute_native(self, intent: Any, context: Dict[str, Any]) -> Any:
        """
        Optional: Perform native automation (legacy/API-based).
        If this returns None or raises exception, UI Vision fallback is used.
        """
        return None

    @property
    def capabilities(self) -> Dict[str, List[str]]:
        """
        Return metadata about supported modes and actions.
        Must be strictly declared by adapters.
        Example:
        {
          "send_message": ["native", "ui"],
          "open_app": ["native"],
          "attach_file": ["ui"]
        }
        """
        caps = {action: ["ui"] for action in self.supported_actions}
        
        # Implicitly support generic UI actions if we are compliant with BasePlatformAdapter
        # But wait, caps is static property access usually? No, it's a property on the instance.
        # But capabilities() doesn't take context?
        # The Planner checks capabilities BEFORE calling build_plan but AFTER resolving.
        # If resolve picks us, it checks capabilities[action].
        
        # We need to expose 'click' capability if we support it via context logic.
        # Since context logic is dynamic, we should probably declare 'click' as supported via UI
        # in a broad sense, or rely on the Planner's "fallback" to UI if not explicitly native.
        
        # Let's say we support 'click' via UI for ALL adapters by default if they inherit this?
        # No, that breaks the "Strict Capability" rule.
        
        # Use a wildcard capability
        caps["*"] = ["ui"] 
        return caps
