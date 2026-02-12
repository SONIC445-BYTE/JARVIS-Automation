import os
import importlib.util
import sys
from typing import Any, List, Dict
from .adapters.base_adapter import BasePlatformAdapter
from .adapter_registry import registry
from .utils.capability_index import capability_index

class AdapterShim(BasePlatformAdapter):
    """Wraps legacy or incomplete adapters to ensure contract compliance."""
    
    def __init__(self, legacy_adapter: Any):
        self.legacy = legacy_adapter
        self.platform = getattr(legacy_adapter, 'platform_name', 'unknown')
        self.supported_actions = getattr(legacy_adapter, 'supported_actions', [])
        print(f"[AdapterShim] Wrapped {self.platform} (Legacy/Incomplete)")

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        # NEW: Context Awareness for Shims
        active_app = context.get("active_app", "").lower()
        my_platform = self.platform.lower()
        
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        
        if active_app and active_app == my_platform:
             if action in ["click", "type", "scroll", "wait"]:
                 return True
                 
        return action in self.supported_actions

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Heuristic: If legacy has build_plan, use it. Otherwise, default UI fallback.
        if hasattr(self.legacy, 'build_plan'):
            try:
                # Some legacy adapters might return a different Plan object
                action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
                res = self.legacy.build_plan(action, intent if isinstance(intent, dict) else {})
                if hasattr(res, 'steps'):
                    return [{"type": s.action if hasattr(s, 'action') else s.get('type'), 
                             "target": s.target if hasattr(s, 'target') else s.get('target'),
                             "value": getattr(s, 'parameters', {}).get('text') or s.get('value')} for s in res.steps]
            except Exception as e:
                print(f"[AdapterShim] Failed to use legacy planning for {self.platform}: {e}")
        
        # Default UI Fallback
        target = intent.get("target") or intent.get("raw", "unknown")
        return [{"type": "ocr_click", "target": target}]

    @property
    def capabilities(self) -> Dict[str, List[str]]:
        return {"*": ["ui_fallback_only"]}

class DynamicAdapterLoader:
    """Scans and registers all adapters from the platform_adapters directory."""
    
    def __init__(self, search_path: str = "AgentCore/platform_adapters"):
        self.search_path = search_path

    def load_all(self):
        print(f"[DynamicLoader] Scanning {self.search_path} for adapters...")
        if not os.path.exists(self.search_path):
            print(f"[DynamicLoader] Path not found: {self.search_path}")
            return

        # 1. Scan for existing adapters
        discovered_folders = []
        for entry in os.scandir(self.search_path):
            if entry.is_dir():
                discovered_folders.append(entry.name)
                adapter_file = os.path.join(entry.path, "adapter.py")
                if os.path.exists(adapter_file):
                    self._load_adapter(entry.path)

        # 2. ENFORCEMENT: Ensure every folder has a registration
        from .adapter_registry import registry
        for folder in discovered_folders:
            # Check if any registered adapter matches this platform
            already_registered = False
            for adapter_list in registry.adapters.values():
                if any(getattr(a, 'platform', '').lower() == folder.lower() for a in adapter_list):
                    already_registered = True
                    break
            
            if not already_registered:
                print(f"[Enforcement] Auto-registering Generic UI Adapter for orphaned folder: {folder}")
                from .adapters.generic_adapters import GenericDesktopAdapter
                # Create a specialized instance for this platform
                shim = GenericDesktopAdapter()
                shim.platform = folder
                shim.supported_actions = ["click", "type", "open", "any"]
                registry.register(shim)
                
                # Update Capability Index
                from .utils.capability_index import capability_index
                capability_index.update(folder, shim.supported_actions, ["ui"])

    def _load_adapter(self, adapter_dir: str):
        try:
            module_name = f"AgentCore.platform_adapters.{os.path.basename(adapter_dir)}.adapter"
            file_path = os.path.join(adapter_dir, "adapter.py")
            
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find classes that look like adapters
            found_registration = False
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and (issubclass(attr, BasePlatformAdapter) or hasattr(attr, 'supported_actions')) and attr_name != 'BasePlatformAdapter' and attr_name != 'BaseAdapter':
                    
                    instance = attr()
                    if not isinstance(instance, BasePlatformAdapter):
                        # Auto-wrap if it doesn't meet the new contract
                        instance = AdapterShim(instance)
                    
                    registry.register(instance)
                    
                    # Update Capability Index
                    capability_index.update(
                        instance.platform, 
                        instance.supported_actions, 
                        ["ui"] + (["native"] if hasattr(instance, 'execute_native') else [])
                    )
                    found_registration = True
            
            if found_registration:
                print(f"[DynamicLoader] Loaded platform: {os.path.basename(adapter_dir)}")
        except Exception as e:
            print(f"[DynamicLoader] Failed to load {adapter_dir}: {e}")

if __name__ == "__main__":
    if "--audit" in sys.argv:
        loader = DynamicAdapterLoader()
        loader.load_all()
        
        from .adapter_registry import registry
        
        # Count unique folders
        search_path = "AgentCore/platform_adapters"
        folders = [f.name for f in os.scandir(search_path) if f.is_dir()]
        print(f"Total folders found: {len(folders)}")
        
        # Unique platforms registered
        platforms = set()
        for action_adapters in registry.adapters.values():
            for a in action_adapters:
                if hasattr(a, 'platform'):
                    platforms.add(a.platform.lower())
        
        print(f"Total platforms registered: {len(platforms)}")
        
        # Verify orphans
        for f in folders:
            if f.lower() not in platforms:
                print(f"🚨 FAILED: Folder {f} not protected!")
            else:
                # Check if it was protected by Generic or Shim
                is_protected = False
                for action_adapters in registry.adapters.values():
                    for a in action_adapters:
                        if getattr(a, 'platform', '').lower() == f.lower():
                            is_protected = True
                            break
                    if is_protected: break
                
        print("Capability index written to data/platform_index.json")
        # Ensure directory exists for index
        os.makedirs("data", exist_ok=True)
        capability_index.save("data/platform_index.json")
        print("--- Audit Complete ---")
