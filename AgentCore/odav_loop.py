"""
ODAV Loop - Simplified Orchestrator
=====================================
Lightweight ODAV wrapper that uses existing Sprint modules.

Sprint 7: Gap Fixes - Agent Loop Integration
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class ODAVPhase(Enum):
    """Current phase of ODAV loop."""
    OBSERVE = "observe"
    DECIDE = "decide"
    ACT = "act"
    VERIFY = "verify"


@dataclass
class ODAVResult:
    """Result of ODAV execution."""
    success: bool
    message: str
    phase_reached: ODAVPhase
    steps_executed: int
    execution_time_ms: int
    reflection: Optional[str] = None
    # Phase 2g: True when a browser adapter hit a CAPTCHA/login-wall.
    # Distinct from success=False -- a block is a pause awaiting a human,
    # not a failure. jarvis.py's conversation loop checks this to decide
    # whether to report failure or start the pending-resume flow.
    blocked: bool = False


class ODAVLoop:
    """
    Simplified ODAV orchestrator using Sprint 2-6 modules.
    
    Observe → Decide → Act → Verify (with self-correction)
    
    This wraps existing modules into a coherent loop:
    - ui_inspector for OBSERVE
    - intent_planner + task_graph for DECIDE  
    - ui_executor for ACT
    - action_recovery + self_reflection for VERIFY
    """
    
    MAX_RETRIES = 3
    
    def __init__(self):
        # Lazy load modules
        self._inspector = None
        self._planner = None
        self._executor = None
        self._recovery = None
        self._reflection = None
        self._router = None
        
        self._execution_log: List[Dict] = []
    
    def _init_modules(self):
        """Initialize modules on first use."""
        if self._planner is not None:
            return
        
        try:
            from .ui_inspector import UIInspector
            from .intent_planner import IntentPlanner
            from .ui_executor import UIExecutor
            from .action_recovery import ActionRecovery
            from .self_reflection import SelfReflection
            from .intent_router import IntentRouter
            
            self._inspector = UIInspector()
            self._planner = IntentPlanner()
            self._executor = UIExecutor()
            self._recovery = ActionRecovery()
            self._reflection = SelfReflection()
            self._router = IntentRouter()
            
            print("[ODAV] Modules initialized")
            
        except ImportError as e:
            print(f"[ODAV] Module import error: {e}")
    
    def execute(self, command: str) -> ODAVResult:
        """
        Execute a command through ODAV loop.
        
        Args:
            command: Natural language command
            
        Returns:
            ODAVResult with execution details
        """
        start_time = time.time()
        self._init_modules()
        
        print(f"\n{'='*50}")
        print(f"[ODAV] Command: {command}")
        print(f"{'='*50}")
        
        try:
            # Route intent first
            if self._router:
                intent_result = self._router.classify(command)
                if intent_result.handler == "llm":
                    # This is a conversation, not an action
                    return ODAVResult(
                        success=True,
                        message="Routed to conversation handler",
                        phase_reached=ODAVPhase.DECIDE,
                        steps_executed=0,
                        execution_time_ms=int((time.time() - start_time) * 1000)
                    )

                resolved_intent = intent_result.extracted_entities.get("resolved_intent")
                if resolved_intent is not None and self._executor is not None:
                    # Phase 2a: a platform+action adapter command was
                    # resolved (e.g. "send a whatsapp message to X saying
                    # Y") -- dispatch it directly through the adapter
                    # registry instead of the OBSERVE/DECIDE plan pipeline,
                    # which has no concept of send_message/read_unread.
                    print(f"\n[ODAV] Resolved adapter command: {resolved_intent.adapter}.{resolved_intent.action}")
                    exec_result = self._executor.execute_intent(resolved_intent)

                    from AgentCore.ui_executor import ExecutionStatus
                    if exec_result.status == ExecutionStatus.BLOCKED:
                        # Phase 2g: a CAPTCHA/login-wall, not a failure --
                        # message is the honest, physician-facing reason;
                        # blocked=True tells the caller (jarvis.py) to
                        # start the pending-resume flow instead of
                        # reporting an error.
                        return ODAVResult(
                            success=False,
                            message=exec_result.error or "Blocked, waiting for you to complete a step manually.",
                            phase_reached=ODAVPhase.VERIFY,
                            steps_executed=0,
                            execution_time_ms=int((time.time() - start_time) * 1000),
                            blocked=True,
                        )

                    return ODAVResult(
                        success=exec_result.ok,
                        message=exec_result.error or f"{resolved_intent.action} on {resolved_intent.adapter}: {'OK' if exec_result.ok else 'FAILED'}",
                        phase_reached=ODAVPhase.VERIFY,
                        steps_executed=1 if exec_result.ok else 0,
                        execution_time_ms=int((time.time() - start_time) * 1000)
                    )
            
            # ============ OBSERVE ============
            print("\n[OBSERVE] Scanning environment...")
            ui_state = {}
            if self._inspector:
                ui_state = self._inspector.get_current_state()
                print(f"  Active window: {ui_state.get('active_window', 'unknown')}")
                print(f"  Elements found: {len(ui_state.get('elements', []))}")
            
            # ============ DECIDE ============
            print("\n[DECIDE] Planning actions...")
            plan = None
            if self._planner:
                plan = self._planner.plan(command)
                if plan and plan.steps:
                    print(f"  Steps planned: {len(plan.steps)}")
                    for i, step in enumerate(plan.steps[:3]):
                        print(f"    {i+1}. {step.action}: {step.target}")
                else:
                    # Fallback: treat as simple command
                    plan = self._create_simple_plan(command)
            else:
                plan = self._create_simple_plan(command)
            
            if not plan or not plan.steps:
                return ODAVResult(
                    success=False,
                    message="Could not create execution plan",
                    phase_reached=ODAVPhase.DECIDE,
                    steps_executed=0,
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )
            
            # ============ ACT + VERIFY (loop) ============
            steps_executed = 0
            last_error = None
            
            for step in plan.steps:
                retries = 0
                step_success = False
                
                while retries < self.MAX_RETRIES and not step_success:
                    print(f"\n[ACT] Step {steps_executed + 1}: {step.action} - {step.target}")
                    
                    # Execute
                    if self._executor:
                        result = self._executor.execute_step(step)
                    else:
                        result = self._execute_fallback(step)
                    
                    # ============ VERIFY ============
                    print(f"[VERIFY] Checking result...")
                    
                    if result.success:
                        print(f"  ✓ Step succeeded")
                        steps_executed += 1
                        step_success = True
                    else:
                        print(f"  ✗ Step failed: {result.error}")
                        last_error = result.error
                        
                        # Self-reflection
                        if self._reflection:
                            analysis = self._reflection.analyze(
                                {"type": step.action, "target": step.target},
                                result.error,
                                ui_state
                            )
                            print(f"  [REFLECT] {analysis.root_cause}")
                            
                            if analysis.should_retry:
                                retries += 1
                                print(f"  [RETRY] Attempt {retries}/{self.MAX_RETRIES}")
                                time.sleep(0.5 * retries)
                            else:
                                break
                        else:
                            retries += 1
                
                if not step_success:
                    # Recovery failed
                    reflection_msg = None
                    if self._reflection:
                        reflection_msg = self._reflection.explain_failure(analysis)
                    
                    return ODAVResult(
                        success=False,
                        message=f"Failed at step {steps_executed + 1}: {last_error}",
                        phase_reached=ODAVPhase.VERIFY,
                        steps_executed=steps_executed,
                        execution_time_ms=int((time.time() - start_time) * 1000),
                        reflection=reflection_msg
                    )
            
            # All steps succeeded
            return ODAVResult(
                success=True,
                message=f"Completed {steps_executed} steps successfully",
                phase_reached=ODAVPhase.VERIFY,
                steps_executed=steps_executed,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            return ODAVResult(
                success=False,
                message=f"Execution error: {str(e)}",
                phase_reached=ODAVPhase.ACT,
                steps_executed=0,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _create_simple_plan(self, command: str):
        """Create a minimal plan for simple commands."""
        from .intent_planner import ActionPlan, ExecutionStep
        
        # Parse simple commands
        command_lower = command.lower()
        
        steps = []
        
        if "open " in command_lower:
            app_name = command_lower.split("open ", 1)[1].strip()
            steps.append(ExecutionStep(
                action="open_app",
                target=app_name,
                parameters={}
            ))
        elif "close " in command_lower:
            steps.append(ExecutionStep(
                action="close_app",
                target="current",
                parameters={}
            ))
        elif "click " in command_lower:
            target = command_lower.split("click ", 1)[1].strip()
            steps.append(ExecutionStep(
                action="click",
                target=target,
                parameters={}
            ))
        elif "type " in command_lower:
            text = command.split("type ", 1)[1].strip()
            steps.append(ExecutionStep(
                action="type",
                target=text,
                parameters={}
            ))
        elif "play " in command_lower:
            query = command.split("play ", 1)[1].strip()
            import urllib.parse
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            steps.append(ExecutionStep(
                action="navigate",
                target=url,
                parameters={"url": url}
            ))

        return ActionPlan(plan_id="simple", intent_text=command, steps=steps)
    
    def _execute_fallback(self, step) -> Any:
        """Fallback execution without full executor."""
        import subprocess
        from dataclasses import dataclass
        
        @dataclass
        class FallbackResult:
            success: bool
            error: str = ""
        
        try:
            if step.action == "open_app":
                subprocess.Popen(f'start "" "{step.target}"', shell=True)
                time.sleep(1)
                return FallbackResult(success=True)
            
            return FallbackResult(success=False, error="Action not supported in fallback")
            
        except Exception as e:
            return FallbackResult(success=False, error=str(e))


def run_odav(command: str) -> ODAVResult:
    """Convenience function to run ODAV loop."""
    loop = ODAVLoop()
    return loop.execute(command)


def test_odav():
    """Test ODAV loop."""
    print("ODAV Loop Test")
    print("=" * 50)
    
    result = run_odav("open notepad")
    print(f"\nResult: {result.success}")
    print(f"Message: {result.message}")
    print(f"Phase: {result.phase_reached.value}")
    print(f"Steps: {result.steps_executed}")


if __name__ == "__main__":
    test_odav()
