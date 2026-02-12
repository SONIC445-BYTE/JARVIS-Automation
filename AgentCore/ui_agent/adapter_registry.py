from typing import Dict, Any, List, Optional, Type

class AdapterRegistry:
    """
    Central authority for all platform adapters in JARVIS.
    Maps actions to registered adapters.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AdapterRegistry, cls).__new__(cls)
            cls._instance.adapters = {} # action -> list of adapters
            cls._instance.platform_index = {} # platform_name -> list of adapters
        return cls._instance

    def register(self, adapter_instance):
        """Register an adapter instance based on its supported actions."""
        # 1. Action Mapping
        for action in adapter_instance.supported_actions:
            if action not in self.adapters:
                self.adapters[action] = []
            if adapter_instance not in self.adapters[action]:
                self.adapters[action].append(adapter_instance)
        
        # 2. Platform Mapping
        p = getattr(adapter_instance, 'platform', 'generic')
        if p not in self.platform_index:
            self.platform_index[p] = []
        if adapter_instance not in self.platform_index[p]:
            self.platform_index[p].append(adapter_instance)
            
        print(f"[AdapterRegistry] Registered {adapter_instance.__class__.__name__} for {adapter_instance.supported_actions} (Platform: {p})")

    def resolve(self, action: str, platform: Optional[str] = None) -> List[Any]:
        """
        Find candidates for a given action and optional platform.
        Output is ranked.
        """
        candidates = self.adapters.get(action, [])
        candidates = list(candidates) # Copy to avoid mutating original list referenced by dict? 
        # Actually self.adapters[action] gives a list. We should make a new list.
        
        if platform:
             # Add platform specific adapters even if they didn't register for 'action'
             # They might handle it dynamically via can_handle (Context Aware)
             p_candidates = self.platform_index.get(platform, [])
             for pc in p_candidates:
                 if pc not in candidates:
                     candidates.append(pc)
        
        # Also include generic/fallback adapters if potentially relevant
        # But we rely on can_handle to filter them out later, or we explicitly append them here
        # For now, let's trust the 'candidates' list contains what registered for this execution
        # But wait, generic adapters might register for specific actions too?
        # If 'any' is in adapters, we should consider them too?
        
        all_candidates = list(candidates)
        # Add 'any' or '*' adapters if not already there
        for fallback_key in ["any", "*"]:
            for adapter in self.adapters.get(fallback_key, []):
                if adapter not in all_candidates:
                    all_candidates.append(adapter)
        
        def score(adapter):
            s = 0
            # 1. Platform Specificity
            if platform and getattr(adapter, 'platform', '').lower() == platform.lower():
                s += 100
            elif getattr(adapter, 'platform', '') == 'generic':
                 s += 10
            
            # 2. Capability Strength
            caps = getattr(adapter, 'capabilities', {})
            # caps is now guaranteed to be Dict[str, List[str]] due to base class
            # But we must be careful with 'any' fallback shims
            modes = caps.get(action, [])
            if not modes and "*" in caps:
                 modes = caps["*"]
            
            if "native" in modes:
                s += 50
            elif "ui" in modes:
                s += 20
            elif "ui_fallback_only" in modes:
                s += 5 # Low priority for shims
            
            # 3. Penalize GenericDesktop for non-desktop actions
            if adapter.__class__.__name__ == "GenericDesktopAdapter" and "desktop" not in (platform or ""):
                s -= 50
                
            return s

        # Sort descending by score
        all_candidates.sort(key=score, reverse=True)
        return all_candidates

# Global registry instance
registry = AdapterRegistry()
