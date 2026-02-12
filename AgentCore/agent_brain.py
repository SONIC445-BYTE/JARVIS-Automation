"""
Agent Brain - Main ODAV Loop Orchestrator
==========================================
Coordinates all layers to execute intents autonomously.

ODAV Loop:
1. OBSERVE - Scan UI state
2. DECIDE - Parse intent, plan steps
3. ACT - Execute actions
4. VERIFY - Check success, recover if needed
"""

import time
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import uuid

from .intent_parser import IntentParser, Intent
from .llm_command_parser import LLMCommandParser, ActionStep
from .task_planner import TaskPlanner, ExecutionPlan, ExecutionStep
from .ui_perception import UIScanner
from .action_executor import ActionExecutor
from .validation_engine import ValidationEngine, RecoveryAction
from .checkpoint import CheckpointManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentBrain:
    """
    Main orchestrator for the ODAV Agent Engine.
    
    Executes natural language commands through:
    Observe → Decide → Act → Verify loop
    
    Every execution is:
    - Logged
    - Checkpointed
    - Recoverable
    """
    
    def __init__(self, use_llm_parser: bool = True):
        """Initialize the AgentBrain.
        
        Args:
            use_llm_parser: Whether to use the LLM-based command parser
        """
        self.parser = IntentParser()
        self.planner = TaskPlanner()
        self.scanner = UIScanner()
        self.executor = ActionExecutor()
        self.validator = ValidationEngine()
        self.checkpoints = CheckpointManager()
        
        # Initialize LLM command parser if enabled
        self.use_llm_parser = use_llm_parser
        self.llm_parser = LLMCommandParser() if use_llm_parser else None
        
        # Execution state
        self.current_intent: Optional[Union[Intent, Dict]] = None
        self.current_plan: Optional[ExecutionPlan] = None
        self.execution_log: List[Dict] = []
        
        logger.info(f"AgentBrain initialized with LLM parser: {use_llm_parser}")
        
    def _parse_command(self, raw_command: str) -> Dict[str, Any]:
        """
        Parse a natural language command into an intent.
        
        Args:
            raw_command: The command to parse
            
        Returns:
            Dict containing the parsed intent
        """
        # Check if we should use the LLM parser
        use_llm = self.use_llm_parser and self.llm_parser and self._should_use_llm_parser(raw_command)
        
        if use_llm:
            logger.info(f"Using LLM parser for command: {raw_command}")
            try:
                # Try to parse with LLM first
                actions = self.llm_parser.parse(raw_command)
                if not actions:
                    raise ValueError("LLM parsed no actions (empty list).")
                    
                logger.debug(f"LLM parsed actions: {actions}")
                
                # Convert to intent format
                return {
                    "intent_id": f"llm_{str(uuid.uuid4())[:8]}",
                    "raw_command": raw_command,
                    "action": "llm_sequence",
                    "is_deterministic": False,
                    "confidence": 0.9,  # High confidence for LLM parsing
                    "mode": "ui_wait",
                    "parameters": {
                        "actions": actions
                    }
                }
            except Exception as e:
                logger.warning(f"LLM parsing failed, falling back to rule-based: {e}")
                
        # Fall back to rule-based parsing
        logger.info(f"Using rule-based parser for command: {raw_command}")
        intent = self.parser.parse(raw_command)
        return intent.to_dict()
    
    def _should_use_llm_parser(self, command: str) -> bool:
        """Determine if we should use the LLM parser for this command."""
        # Use LLM for complex commands with multiple steps or conjunctions
        if any(connector in command.lower() for connector in [" and ", " then ", " after ", " next "]):
            return True
            
        # Use LLM for commands that might need context understanding
        complex_actions = ["search", "find", "navigate", "go to", "open", "click", "type"]
        if any(action in command.lower() for action in complex_actions):
            return True
            
        return False
    
    def _create_execution_plan(self, intent: Dict) -> ExecutionPlan:
        """Create an execution plan from an intent."""
        # Handle LLM-parsed actions
        if intent.get("action") == "llm_sequence":
            actions = intent.get("parameters", {}).get("actions", [])
            steps = []
            
            for i, action in enumerate(actions):
                step = ExecutionStep(
                    step_id=f"llm_step_{i+1}",
                    step_number=len(steps) + 1,
                    action=action.get("action", "unknown"),
                    target=action.get("target", ""),
                    parameters=action.get("parameters", {}),
                    requires_ui_scan=action.get("requires_ui_scan", False),
                    verification_condition=action.get("verification_condition", ""),
                    status="pending"
                )
                steps.append(step)
            
            return ExecutionPlan(
                plan_id=f"plan_{str(uuid.uuid4())[:8]}",
                intent_id=intent.get("intent_id", "unknown"),
                steps=steps,
                total_steps=len(steps)
            )
            
        # Fall back to standard planning
        return self.planner.create_plan(intent)
    
    def execute_command(self, raw_command: str) -> Dict[str, Any]:
        """
        Execute a natural language command through ODAV loop.
        
        Args:
            raw_command: Natural language command from user
            
        Returns:
            Dict with execution result and details
        """
        start_time = datetime.now()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"AGENT BRAIN: Processing command: '{raw_command}'")
        logger.info(f"{'='*60}\n")
        
        result = {
            "command": raw_command,
            "status": "pending",
            "message": "",
            "steps_executed": 0,
            "steps_total": 0,
            "execution_time_ms": 0,
        }
        
        try:
            # =========================================
            # STEP 1: DECIDE - Parse Intent
            # =========================================
            logger.info("[DECIDE] Parsing intent...")
            intent_data = self._parse_command(raw_command)
            self.current_intent = intent_data
            
            result["intent_id"] = intent_data.get("intent_id", "unknown")
            result["is_deterministic"] = intent_data.get("is_deterministic", False)
            
            # Check if this should go to legacy system
            if intent_data.get("is_deterministic") and not self.parser.requires_agent_core(intent_data):
                logger.info("[DECIDE] Deterministic command - could use legacy system")
                # Continue with agent for now (can route later)
            
            # =========================================
            # STEP 2: DECIDE - Create Plan
            # =========================================
            logger.info("[DECIDE] Creating execution plan...")
            plan = self._create_execution_plan(intent_data)
            self.current_plan = plan
            
            # FAIL FAST: Validate plan before execution
            if not plan.steps:
                error_msg = f"Plan contains no steps for command: '{raw_command}'"
                logger.warning(error_msg)
                result["status"] = "failed"
                result["message"] = error_msg
                return result

            for step in plan.steps:
                if step.action == "unknown":
                    error_msg = f"Plan contains unknown action. Aborting execution for command: '{raw_command}'"
                    logger.error(error_msg)
                    result["status"] = "failed"
                    result["message"] = error_msg
                    return result
            
            result["steps_total"] = plan.total_steps
            print(f"[DECIDE] Plan created with {plan.total_steps} steps")
            
            # =========================================
            # STEP 3: ODAV LOOP - Execute Plan
            # =========================================
            plan.status = "executing"
            
            while True:
                step = plan.get_current_step()
                if not step:
                    plan.status = "completed"
                    break
                
                step_num = plan.current_step
                logger.info(f"\n[STEP {step_num + 1}/{plan.total_steps}] {step.action}: {step.target}")
                
                # Final safety check before execution
                if step.action == "unknown":
                     logger.error(f"[FATAL] Attempted to execute 'unknown' action. Aborting.")
                     plan.status = "aborted"
                     result["status"] = "failed"
                     result["message"] = "Execution Aborted: Unknown Action"
                     break
                     
                step.status = "executing"
                
                try:
                    # ----- OBSERVE -----
                    logger.debug("  [OBSERVE] Scanning UI...")
                    ui_snapshot = self.scanner.scan()
                    
                    # Create checkpoint
                    active_win, _ = self.scanner.get_active_window()
                    self.checkpoints.create_checkpoint(
                        step_number=step_num,
                        active_window=active_win,
                        ui_tree=ui_snapshot.to_dict(),
                        intent_id=result["intent_id"],
                        notes=f"Before step: {step.action}"
                    )
                    
                    # ----- ACT -----
                    logger.debug(f"  [ACT] Executing action: {step.action}")
                    action_dict = self._step_to_action(step, ui_snapshot)
                    action_result = self.executor.execute(action_dict)
                    
                    # ----- VERIFY -----
                    logger.debug("  [VERIFY] Checking result...")
                    # Give UI time to update
                    time.sleep(0.3)
                    new_snapshot = self.scanner.scan()
                    
                    # Convert step to dict if it's an object
                    step_dict = step.to_dict() if hasattr(step, 'to_dict') else step
                    
                    verification = self.validator.verify_step(
                        step_dict,
                        action_result.to_dict() if hasattr(action_result, 'to_dict') else {},
                        new_snapshot.to_dict()
                    )
                    
                    # Handle verification result
                    if verification.success:
                        logger.info("  [VERIFY] ✓ Step succeeded")
                        step.status = "success"
                        result["steps_executed"] += 1
                        
                        if hasattr(step, 'step_id'):
                            self.validator.reset_retries(step.step_id)
                        
                        if not plan.advance():
                            plan.status = "completed"
                            logger.info("\n[COMPLETE] All steps executed successfully!")
                            break
                        
                        # If we get here, there are more steps to execute
                        continue
                    else:
                        logger.warning(f"  [VERIFY] ✗ Step failed: {verification.message}")
                        step.status = "failed"
                        
                        try:
                            # Handle recovery
                            if verification.recovery_action == RecoveryAction.RETRY:
                                logger.info("  [RECOVER] Retrying step...")
                                continue  # Retry same step
                                
                            elif verification.recovery_action == RecoveryAction.REPLAN:
                                logger.info("  [RECOVER] Replanning from current step...")
                                plan = self.planner.replan_from_step(
                                    plan, step_num,
                                    verification.message,
                                    new_snapshot.to_dict()
                                )
                                self.current_plan = plan
                                continue
                                
                            else:  # ABORT
                                logger.error("  [ABORT] Cannot recover, aborting execution")
                                plan.status = "aborted"
                                result["status"] = "failed"
                                result["message"] = verification.message
                                break
                                
                        except Exception as e:
                            logger.error(f"  [ERROR] Recovery failed: {e}")
                            plan.status = "aborted"
                            result["status"] = "error"
                            result["message"] = f"Recovery failed: {e}"
                            break
                            
                except Exception as e:
                    logger.error(f"  [ERROR] Error during step execution: {e}")
                    step.status = "error"
                    result["status"] = "error"
                    result["message"] = f"Step execution failed: {e}"
                    break
            
            # Set final result
            if plan.status == "completed":
                result["status"] = "success"
                result["message"] = f"Command executed successfully in {plan.total_steps} steps"
            elif plan.status != "aborted":
                result["status"] = plan.status
                result["message"] = "Execution completed"
                
            result["execution_time_ms"] = int((datetime.now() - start_time).total_seconds() * 1000)
            
        except Exception as e:
            logger.exception("Agent execution failed")
            result["status"] = "error"
            result["message"] = str(e)
            result["execution_time_ms"] = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Log the full error for debugging
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error("Full traceback:\n" + ''.join(traceback.format_tb(e.__traceback__)))
        
        # Log execution
        self.execution_log.append(result)
        
        # Log final result
        logger.info(f"\n{'='*60}")
        logger.info(f"AGENT BRAIN: Result - {result['status']}")
        if result['status'] != 'success':
            logger.warning(f"Error: {result.get('message', 'No error message')}")
        logger.info(f"{'='*60}\n")
        
        return result
    
    def _step_to_action(self, step, ui_snapshot) -> Dict[str, Any]:
        """Convert execution step to action dict for executor."""
        # Handle both ExecutionStep and dict for backward compatibility
        action_type = step.action if hasattr(step, 'action') else step.get('action', '')
        target = step.target if hasattr(step, 'target') else step.get('target', '')
        params = step.parameters if hasattr(step, 'parameters') else step.get('parameters', {})
        
        action = {
            "type": action_type,
        }
        
        if action_type == "click":
            # Find element if requires UI scan
            requires_ui_scan = step.requires_ui_scan if hasattr(step, 'requires_ui_scan') else step.get('requires_ui_scan', False)
            
            if requires_ui_scan and ui_snapshot:
                try:
                    element = self.scanner.find_element(target, ui_snapshot)
                    if element:
                        action["x"] = element.center[0]
                        action["y"] = element.center[1]
                        action["element_name"] = getattr(element, 'name', str(element))
                    else:
                        # Try position-based selection
                        selector = params.get("selector")
                        if selector:
                            element = self.scanner.find_by_position(selector, ui_snapshot)
                            if element:
                                action["x"] = element.center[0]
                                action["y"] = element.center[1]
                                action["element_name"] = f"{selector}:{getattr(element, 'name', str(element))}"
                except Exception as e:
                    logger.warning(f"Error finding element for click: {e}")
            
        elif action_type == "type":
            action["text"] = target
            
        elif action_type == "hotkey":
            action["keys"] = params.get("keys", [])
            
        elif action_type == "scroll":
            action["direction"] = target
            action["amount"] = 3
            
        elif action_type == "open_app":
            action["app_name"] = target
            
        elif action_type == "close_app":
            action["app_name"] = target if target != "current_window" else None
            
        elif action_type == "navigate":
            action["url"] = target if target.startswith(('http://', 'https://')) else f'https://{target}'
            
        elif action_type == "search":
            action["query"] = target
            
        elif action_type == "wait":
            action["seconds"] = float(step.target) if step.target else 1
            
        elif step.action == "ui_scan":
            # UI scan is implicit, just wait briefly
            action["type"] = "wait"
            action["seconds"] = 0.5
            
        elif step.action == "navigate_to":
            # Navigate in file explorer
            action["type"] = "hotkey"
            action["keys"] = ["ctrl", "l"]
            # This would need follow-up steps to type path
            
        elif step.action == "send":
            action["type"] = "send"
            
        return action
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current agent state for debugging."""
        try:
            intent_data = None
            if self.current_intent:
                if hasattr(self.current_intent, 'to_dict'):
                    intent_data = self.current_intent.to_dict()
                elif isinstance(self.current_intent, dict):
                    intent_data = self.current_intent
                    
            plan_data = None
            if self.current_plan and hasattr(self.current_plan, 'to_dict'):
                plan_data = self.current_plan.to_dict()
                
            return {
                "timestamp": datetime.now().isoformat(),
                "intent": intent_data,
                "plan": plan_data,
                "execution_log": self.execution_log[-10:],  # Last 10 commands
                "llm_parser_enabled": self.use_llm_parser
            }
        except Exception as e:
            logger.error(f"Error getting current state: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def reset(self):
        """Reset agent state."""
        self.current_intent = None
        self.current_plan = None
        self.executor.clear_history()
        self.validator.reset_retries()
        # Keep checkpoints for debugging


# Convenience function for integration
def run_agent_command(command: str) -> Dict[str, Any]:
    """Convenience function to run a command through AgentBrain."""
    agent = AgentBrain()
    return agent.execute_command(command)
