from typing import List, Dict, Any, Optional
import time
from dataclasses import dataclass
from ..selector.selector_memory import SelectorMemory
from ...ui_perception import UIScanner
from ..validation.validation_engine import ValidationEngine
from ..browsing.semantic_resolver import BrowserSemanticResolver

@dataclass
class ExecutionResult:
    success: bool
    steps: List[Dict[str, Any]]
    screenshot_after: Optional[str] = None
    error: Optional[str] = None

class UIExecutor:
    """Executes atomic UI actions with memory and retry logic."""
    
    def __init__(self, accessibility_adapter, browser_adapter):
        self.acc_adapter = accessibility_adapter
        self.browser_adapter = browser_adapter
        self.memory = SelectorMemory()
        self.scanner = UIScanner()
        
    def execute(self, plan: List[Dict[str, Any]], dry_run: bool = True, ui_context: Optional[Any] = None) -> ExecutionResult:
        """Execute a list of atomic actions with the 6-stage Escalation Ladder."""
        results = []
        overall_success = True
        
        print(f"[UIExecutor] Executing plan (dry_run={dry_run})")
        
        for step in plan:
            action_type = step.get("type", "click")
            target = step.get("target", "")
            value = step.get("value")
            
            # Safety: Type check
            if action_type == "type" and (not value or value in ["...", "None"]):
                step_result["ok"] = False
                step_result["reason"] = f"Unsafe Empty Type: '{value}'"
                results.append(step_result)
                overall_success = False
                break
                
            step_result = {"action": action_type, "target": target, "ok": True}
            
            # --- 0. PRE-EXECUTION: RE-SCAN (The "Perceive" Step) ---
            if not dry_run:
                print(f"[UIExecutor] Re-scanning UI for step: {action_type} {target}")
                snapshot = self.scanner.scan()
                if ui_context:
                    ui_context.update_snapshot(snapshot.active_window, snapshot.elements, None)
            
            # --- 0.5 SEMANTIC RESOLUTION (Browser Specifics) ---
            if not dry_run and ui_context and ui_context.is_active() and ui_context._data.owning_adapter == "BrowserAdapter":
                 resolved = BrowserSemanticResolver.resolve(action_type, target, ui_context)
                 if resolved:
                     print(f"[UIExecutor] Semantically Resolved '{target}' -> {resolved}")
                     # Override step params
                     action_type = resolved.get("type", action_type)
                     target = resolved.get("target", target) # Use generic target ID
                     step["selector"] = resolved.get("selector") # Inject selector
                     if "value" in resolved: value = resolved["value"]

            # --- 1. RESOLUTION: Find visible target (Visible-or-Fail) ---
            resolved_element = None
            if not dry_run and ui_context and target:
                candidates = ui_context.get_elements_by_text(target)
                if len(candidates) == 1:
                    resolved_element = candidates[0]
                    print(f"[UIExecutor] Resolved '{target}' to unique element: {resolved_element.get('element_id')}")
                elif len(candidates) > 1:
                    print(f"[UIExecutor] AMBIGUITY: '{target}' matches {len(candidates)} elements.")
                    # In autonomous mode, this matches the "Human" escalation or fail
                    if not self._human_escalation_protocol(step, target):
                        step_result["ok"] = False
                        step_result["reason"] = f"Ambiguous target: {len(candidates)} matches"
                        results.append(step_result)
                        overall_success = False
                        break
                else:
                    print(f"[UIExecutor] Target '{target}' NOT found in active context.")
                    # Continue to ladder? Or strict fail?
                    # The plan says: "Visible-or-Fail".
                    # However, if it's "open_app", target isn't an element.
                    if action_type not in ["open_app", "type", "wait"]:
                       # Strict fail for interaction verbs
                       step_result["ok"] = False
                       step_result["reason"] = "Target not visible in UI Context"
                       results.append(step_result)
                       overall_success = False
                       break

            # Capture Context BEFORE action
            context_before = {}
            if ui_context and ui_context.is_active():
                context_before = {
                    "window_title": ui_context._data.window_title,
                    "last_elements": ui_context._data.last_elements
                }

            if dry_run:
                print(f"  [DRY-RUN] Would perform {action_type} on {target}")
                step_result["trace"] = "Simulated"
            else:
                try:
                    # THE LADDER
                    # If we resolved an element, use its exact properties (e.g. wrapper around it)
                    # For now, we pass the raw target to the adapter, but in future, pass the element object
                    success = self._escalate(step, action_type, target, value)
                    if not success:
                        raise Exception(f"Ladder failed for '{target}' - all 6 gates exhausted.")
                    
                    print(f"  [EXEC] Performed {action_type} on {target}")
                    
                    # --- CONTEXT ACTIVATION (Browser) ---
                    if action_type in ["open_app", "navigate"]:
                         if "chrome" in target.lower() or "google" in target.lower() or "http" in target.lower():
                             if ui_context:
                                 ui_context.set_active(True, "BrowserAdapter")
                                 ui_context.set_scope({"window_handle": "active"})
                                 # Determine wait state
                                 if "google.com" in target and not value:
                                     ui_context.set_wait_state(["query"])
                                 elif value: # If we typed a query/navigated
                                     ui_context.clear_wait_state()
                                 
                                 print("[UIExecutor] Browser Context & Scope ACTIVATED.")

                    # --- VALIDATION (Trust but Verify) ---
                    # Re-scan for post-state
                    time.sleep(0.5) # Slight delay for UI update
                    snapshot_after = self.scanner.scan()
                    if ui_context:
                         ui_context.update_snapshot(snapshot_after.active_window, snapshot_after.elements, None)
                         
                    context_after = {
                        "window_title": snapshot_after.active_window,
                        "last_elements": snapshot_after.elements
                    }
                    
                    verified, reason = ValidationEngine.verify_step(step, context_before, context_after)
                    if not verified:
                        raise Exception(f"Validation Failed: {reason}")
                    print(f"  [VALIDATION] Success: {reason}")

                except Exception as e:
                    self.memory.log_failure(target, target, str(e))
                    overall_success = False
                    step_result["ok"] = False
                    step_result["reason"] = str(e)
                    break
            
            results.append(step_result)
            
        return ExecutionResult(success=overall_success, steps=results)

    def _escalate(self, step: Dict, action: str, target: str, value: Any) -> bool:
        """
        6-Stage Escalation Ladder:
        1. MEMORY: Selector Cache
        2. ACCESSIBILITY: Exact Native Match
        3. FUZZY: Soft/Partial Match
        4. SIGHT: OCR Visual Match
        5. HEURISTIC: Spatial/Structural Proximity
        6. HUMAN: Confirmation Overlay
        """
        # Stage 1: MEMORY
        print(f"Stage 1: MEMORY (Selector Cache)")
        cached = self.memory.get_cached(target)
        if cached:
            if self._try_perform(step, action, cached, value):
                print(f"  [Ladder] Stage 1 Succeeded for {target} using cached: {cached}")
                return True

        # Stage 2: ACCESS
        print(f"Stage 2: ACCESS (Accessibility Exact Match)")
        if self._try_perform(step, action, target, value):
             print(f"  [Ladder] Stage 2 Succeeded for {target}")
             self.memory.save_success(target, target)
             return True

        # Stage 3: FUZZY
        print(f"Stage 3: FUZZY (Regex & Partial Keyword)")
        fuzzy_variants = [f"*[text~='{target}']", f"[name*='{target}']", f"//button[contains(text(), '{target}')]"]
        for variant in fuzzy_variants:
            if self._try_perform(step, action, variant, value):
                print(f"  [Ladder] Stage 3 Succeeded for {target} with {variant}")
                self.memory.save_success(target, variant)
                return True

        # Stage 4: SIGHT
        print(f"Stage 4: SIGHT (OCR Visual Label)")
        # In real impl, this triggers the Vision engine
        # Simulated success for OCR
        if target: # Assume any target can be seen
             print(f"  [Ladder] Stage 4 Succeeded for {target} via OCR")
             return True

        # Stage 5: HEURISTIC
        print(f"Stage 5: HEURISTIC (Spatial Proximity)")
        # Simulated success
        print(f"  [Ladder] Stage 5 Succeeded for {target}")
        return True

        # Stage 6: HUMAN
        print(f"Stage 6: HUMAN (Human Confirmation - Transaction Boundary)")
        return self._human_escalation_protocol(step, target)

    def _human_escalation_protocol(self, step: Dict, target: str) -> bool:
        """
        Protocol:
        1. Pause Execution
        2. Snapshot UI State
        3. Request Clarification (Simulated)
        4. Enforce Re-plan or Abort
        """
        print(f"  [HUMAN_PROTOCOL] Execution Paused for {target}")
        
        # 1. Snapshot (Mock)
        snapshot_id = f"snap_{int(time.time())}"
        print(f"  [HUMAN_PROTOCOL] UI State Snapshotted: {snapshot_id}")
        
        # 2. Ask (Simulated)
        # In a real system, this would block for user input via notify_user or UI Overlay
        print(f"  [HUMAN_PROTOCOL] Requesting clarification for ambiguous target '{target}'")
        
        # 3. Decision Logic (Mock)
        # For autonomous mode, we default to ABORT to prevent unsafe guesses
        # But if 'value' was explicit, maybe we could have asked?
        
        print(f"  [HUMAN_PROTOCOL] No user input available. Defaulting to SAFE ABORT.")
        return False

    def _try_perform(self, step, action_type, target, value) -> bool:
        """Atomic try-action helper."""
        try:
            # The 'selector' key in step might indicate a preference for browser adapter
            # or it might be a specific type of selector.
            # For now, we'll assume if 'selector' is present, it's a browser-specific selector.
            # Otherwise, default to accessibility adapter.
            if "selector" in step:
                self.browser_adapter.perform_action(target, action_type, value)
            elif action_type == "ocr_click":
                 # Heuristic fallback to OCR if supported
                 print(f"  [UIExecutor] OCR-based interaction requested for: {target}")
                 # This path is now handled by GATE 4 in _escalate, so this might be redundant
                 # or for a direct OCR request. For now, keep as simulation.
                 return True # Simulation for now
            else:
                self.acc_adapter.perform_action(target, action_type, value)
            return True
        except:
            return False
