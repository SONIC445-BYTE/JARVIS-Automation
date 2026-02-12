import os
from typing import List, Dict, Any, Optional, Tuple
from .adapter_registry import registry
from .executor.ui_executor import UIExecutor, ExecutionResult

class NoAdapterFound(Exception):
    pass

class ActionPlanner:
    """
    The Single Authority for generating execution plans in JARVIS.
    Arbitrates between Native and UI Vision adapters via the AdapterRegistry.
    """
    
    @staticmethod
    def plan(intent: Any, context: Dict[str, Any], ui_context: Optional[Any] = None) -> Tuple[Any, List[Dict[str, Any]]]:
        """Returns (selected_adapter, plan) with PlanScore validation."""
        from .utils.capability_index import capability_index
        
        # Extract action and platform from intent (can be dict or object)
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        platform = getattr(intent, 'platform', intent.get('platform') if isinstance(intent, dict) else None)
        
        print(f"[ActionPlanner] Planning for action='{action}', platform='{platform}'")
        
        # 0. Runtime Capability Check (Step 6)
        if platform and platform != "generic":
            idx_caps = capability_index.index.get(platform, {})
            if action not in idx_caps.get("actions", []) and "*" not in idx_caps.get("actions", []):
                 print(f"[ActionPlanner] WARNING: Platform '{platform}' does not declare support for '{action}' in index.")
        
        # 1. Resolve candidates
        # Hint: If intent doesn't specify platform but context does, use context to find platform adapters
        resolve_platform = platform
        if (not resolve_platform or resolve_platform == "generic") and context.get("active_app"):
            resolve_platform = context.get("active_app")
            
        adapters = registry.resolve(action, platform=resolve_platform)
        
        best_adapter = None
        best_plan = []
        best_score = -1.0
        
        for adapter in adapters:
            if not adapter.can_handle(intent, context):
                continue

            # Check Adapter Ownership
            if ui_context and not ui_context.validate_ownership(adapter.__class__.__name__):
                print(f"[ActionPlanner] Skipping {adapter.__class__.__name__} due to ownership mismatch")
                continue
                
            # Step 1: Check declared capabilities
            caps = getattr(adapter, 'capabilities', {})
            modes = caps.get(action, caps.get("*", []))
            
            if not modes:
                # Should have been filtered by can_handle/capabilities, but double check
                pass
                
            # Build plan
            try:
                candidate_plan = adapter.build_plan(intent, context)
            except Exception as e:
                print(f"[ActionPlanner] Plan build failed for {adapter.__class__.__name__}: {e}")
                continue
                
            if not candidate_plan:
                continue

            # Step 3: Calculate PlanScore
            score = 0.0
            
            # Feasibility
            if "native" in modes:
                score += 0.9
            elif "ui" in modes:
                score += 0.6
                if "native" not in modes:
                     score -= 0.1 # Slight penalty for strictly UI
            elif "ui_fallback_only" in modes:
                score += 0.3 # Low confidence fallback
            
            # Specificity
            if getattr(adapter, 'platform', '') == platform:
                score += 0.1
            
            # Step 5: Generic Guardrails
            if adapter.__class__.__name__ == "GenericDesktopAdapter":
                # Penalize generic on non-desktop platforms or complex actions
                if action not in ["navigate", "focus", "open"]:
                     score = 0.0 # Veto
            
            if score > best_score:
                best_score = score
                best_adapter = adapter
                best_plan = candidate_plan
        
        # Validation
        if best_score < 0.3: # Threshold 
             print("[ActionPlanner] No viable plan found above threshold.")
             from .adapters.generic_adapters import UnknownAppFallbackAdapter
             fallback = UnknownAppFallbackAdapter()
             return fallback, fallback.build_plan(intent, context)
             
        # Step 4: Annotation
        print(f"[ActionPlanner] Selected adapter: {best_adapter.__class__.__name__} (Score: {best_score})")
        
        # Determine likely escalation based on capabilities
        adapter_caps = getattr(best_adapter, 'capabilities', {})
        step_modes = adapter_caps.get(action, adapter_caps.get("*", []))
        likely_escalation = "native" if "native" in step_modes else ("ui" if "ui" in step_modes else "human")

        for step in best_plan:
            step["planned_by"] = best_adapter.__class__.__name__
            step["confidence"] = best_score
            step["escalation_likely"] = likely_escalation
            if ui_context:
                step["session_id"] = ui_context.get_session_id()
            
        return best_adapter, best_plan

class NativeUnsupported(Exception):
    pass

class ActionExecutor:
    """
    Handles execution of plans. Tries native first, fallbacks to UI.
    """
    def __init__(self, ui_executor):
        self.ui_executor = ui_executor

    def execute(self, plan: List[Dict[str, Any]], intent: Any, context: Dict[str, Any], adapter: Any = None, ui_context: Any = None) -> ExecutionResult:
        """
        Inverted Execution Logic:
        1. Try Native via adapter (if it provides execute_native)
        2. Fallback to UI Vision for atomic steps
        """
        dry_run = context.get("dry_run", True)
        fallback_level = "unknown"
        adapter_name = adapter.__class__.__name__ if adapter else "none"
        platform_detected = getattr(adapter, 'platform', 'generic')

        # 1. Try Native Fallback
        if adapter and hasattr(adapter, 'execute_native'):
            try:
                print(f"[ActionExecutor] Attempting Native Execution via {adapter_name}")
                native_res = adapter.execute_native(intent, context)
                if native_res is not None:
                    print("[ActionExecutor] Native Execution Succeeded")
                    fallback_level = "native"
                    return ExecutionResult(success=True, steps=[{
                        "action": "native", 
                        "ok": True, 
                        "trace": str(native_res),
                        "platform": platform_detected,
                        "adapter": adapter_name,
                        "fallback": fallback_level
                    }])
            except Exception as e:
                print(f"[ActionExecutor] Native failed: {e}. Falling back to UI Vision.")
        
        # 2. Fallback to UI Vision
        fallback_level = "ui" if adapter else "unknown"
        print(f"[ActionExecutor] Escalating to UI layer (level: {fallback_level})")
        result = self.ui_executor.execute(plan, dry_run=dry_run, ui_context=ui_context)
        
        # Update UI Context on success
        if result.success and ui_context and adapter:
            ui_context.set_active(True, adapter.__class__.__name__)
        
        # Attach traceability metadata to each step result for the audit log
        for step in result.steps:
            step["platform"] = platform_detected
            step["adapter"] = adapter_name
            step["fallback"] = fallback_level

        return result
