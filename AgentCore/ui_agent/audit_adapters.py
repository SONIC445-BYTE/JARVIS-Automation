
import os
import sys
# Ensure imports work from root
sys.path.append(os.getcwd())

from AgentCore.ui_agent.dynamic_loader import DynamicAdapterLoader
from AgentCore.ui_agent.adapter_registry import registry
from AgentCore.ui_agent.action_router import ActionPlanner

def audit_adapters():
    print("=== Master QA: Platform Adapter Follow-Up Audit ===\n")
    
    # 1. Load all adapters
    loader = DynamicAdapterLoader()
    loader.load_all()
    
    results = {
        "passed": [],
        "failed": [], # Relied on UnknownApp/Generic
        "context_aware": []
    }
    
    # Get all unique platforms
    platforms = set()
    for adapters in registry.adapters.values():
        for a in adapters:
            if hasattr(a, 'platform') and a.platform not in ["generic", "unknown", "desktop", "web", "system"]:
                platforms.add(a.platform)
                
    print(f"Auditing {len(platforms)} Platforms: {sorted(list(platforms))}\n")
    
    for platform in sorted(list(platforms)):
        print(f"Testing Platform: {platform}")
        
        # Test 1: Can it handle a generic 'click' when context is set?
        intent = {"action": "click", "target": "test_element", "app": "generic"}
        context = {"active_app": platform}
        
        # We manually invoke planning logic to see who picks it up
        best_adapter = None
        best_score = -1.0
        
        # Mock planner logic roughly
        candidates = registry.resolve("click", None)
        # Add platform specific ones if any claim generic click
        
        # Actually, let's use the real Planner logic but mocked context
        try:
            adapter, plan = ActionPlanner.plan(intent, context)
            adapter_name = adapter.__class__.__name__
            
            print(f"  Result Adapter: {adapter_name}")
            
            if adapter_name == "UnknownAppFallbackAdapter":
                print(f"  ❌ FAIL: Fell back to OCR (No native context awareness)")
                results["failed"].append(platform)
            elif adapter_name == "GenericDesktopAdapter":
                print(f"  ⚠️ WARN: Used GenericDesktop (Check capabilities!)")
                # GenericDesktop is nerfed for click, so this shouldn't happen unless I un-nerfed it or it wasn't registered correctly?
                # Actually, GenericDesktop DOES NOT support 'click' anymore in my previous edit.
                results["failed"].append(platform)
            else:
                # It picked a specific adapter!
                print(f"  ✅ PASS: Handled by {adapter_name}")
                results["passed"].append(platform)
                results["context_aware"].append(platform)
                
        except Exception as e:
            print(f"  ❌ ERROR: Planning crashed: {e}")
            results["failed"].append(platform)
            
        print("-" * 40)

    print("\n=== Audit Summary ===")
    print(f"Total: {len(platforms)}")
    print(f"Passed (Context Aware): {len(results['passed'])} -> {results['passed']}")
    print(f"Failed (Fallback): {len(results['failed'])} -> {results['failed']}")
    
    if len(results["passed"]) == 0:
        print("\nCRITICAL: No adapters are context-aware for follow-up actions!")
    
if __name__ == "__main__":
    audit_adapters()
