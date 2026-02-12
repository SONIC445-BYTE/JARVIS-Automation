"""
Task Planner - Convert Intent to Executable Steps
==================================================
Generates step-by-step execution plans from parsed intents.

Each step is:
- Verifiable
- Recoverable
- State-aware
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
import uuid


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    step_id: str
    step_number: int
    action: str
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_ui_scan: bool = False
    verification_condition: str = ""
    fallback_action: Optional[str] = None
    status: str = "pending"  # pending, executing, success, failed, skipped
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPlan:
    """Complete execution plan for an intent."""
    plan_id: str
    intent_id: str
    steps: List[ExecutionStep]
    total_steps: int
    current_step: int = 0
    status: str = "pending"  # pending, executing, completed, failed, aborted
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['steps'] = [s.to_dict() for s in self.steps]
        return result
    
    def get_current_step(self) -> Optional[ExecutionStep]:
        """Get the current step to execute."""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def advance(self) -> bool:
        """Move to next step. Returns False if plan complete."""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            return True
        return False


class TaskPlanner:
    """
    Convert parsed Intent into executable step sequence.
    
    Generates plans that are:
    - Sequential and ordered
    - Each step is verifiable
    - Recovery-friendly (can re-plan from any step)
    """
    
    # Action templates for common operations
    PLAN_TEMPLATES = {
        "open": [
            {"action": "open_app", "target": "{app}", "verification": "window_exists:{app}"}
        ],
        "close": [
            {"action": "close_app", "target": "{app}", "verification": "window_closed:{app}"}
        ],
        "type": [
            {"action": "type", "target": "{text}", "verification": "text_entered"}
        ],
        "search": [], # Handled dynamically to enforce query presence
        "navigate": [
            {"action": "hotkey", "keys": ["ctrl", "l"], "verification": "address_bar_focused"},
            {"action": "type", "target": "{url}"},
            {"action": "hotkey", "keys": ["enter"], "verification": "page_loaded"}
        ],
        "create_folder": [
            {"action": "open_app", "target": "explorer", "verification": "window_exists:explorer"},
            {"action": "wait", "target": "1"},
            {"action": "navigate_to", "target": "{location}"},
            {"action": "hotkey", "keys": ["ctrl", "shift", "n"], "verification": "new_folder_dialog"},
            {"action": "type", "target": "{name}"},
            {"action": "hotkey", "keys": ["enter"], "verification": "folder_created"}
        ],
        "screenshot": [
            {"action": "hotkey", "keys": ["win", "shift", "s"], "verification": "screenshot_tool"}
        ],
        "download": [
            {"action": "ui_scan", "target": "find_download_element"},
            {"action": "click", "target": "{element}", "requires_ui": True},
            {"action": "wait", "target": "2"},
            {"action": "verify_download", "target": "{filename}"}
        ],
        "upload": [
            {"action": "open_app", "target": "{target_app}"},
            {"action": "ui_scan", "target": "find_upload_button"},
            {"action": "click", "target": "{upload_element}", "requires_ui": True},
            {"action": "wait", "target": "1"},
            {"action": "select_file", "target": "{file_selector}"}
        ],
        "send": [
            {"action": "open_app", "target": "{target_app}", "verification": "window_exists:{target_app}"},
            {"action": "wait", "target": "1"},
            {"action": "type", "target": "{text}", "verification": "text_entered"},
            {"action": "send", "target": "submit", "verification": "send_completed"}
        ]
    }
    
    def __init__(self):
        self.step_counter = 0
        
    def create_plan(self, intent: Dict[str, Any]) -> ExecutionPlan:
        """
        Create execution plan from parsed intent.
        
        Args:
            intent: Parsed intent dict
            
        Returns:
            ExecutionPlan with ordered steps
        """
        action = intent.get("action", "unknown")
        steps: List[ExecutionStep] = []
        
        # Get template for this action
        template = self.PLAN_TEMPLATES.get(action, [])
        
        if action == "search":
             steps = self._build_search_plan(intent)
        elif template:
             steps = self._expand_template(template, intent)
        else:
            # Build custom plan for complex intents
            steps = self._build_custom_plan(intent)
        
        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4())[:8],
            intent_id=intent.get("intent_id", "unknown"),
            steps=steps,
            total_steps=len(steps)
        )
        
        print(f"DEBUG TaskPlanner: Created plan with {len(steps)} steps for action '{action}'")
        return plan
    
    def _expand_template(self, template: List[Dict], intent: Dict) -> List[ExecutionStep]:
        """Expand template with intent parameters."""
        steps = []
        
        for i, step_template in enumerate(template):
            # Replace placeholders with actual values
            target = step_template.get("target", "")
            target = self._replace_placeholders(target, intent)
            
            verification = step_template.get("verification", "")
            verification = self._replace_placeholders(verification, intent)
            
            step = ExecutionStep(
                step_id=f"step_{self.step_counter}",
                step_number=i,
                action=step_template.get("action", ""),
                target=target,
                parameters={"keys": step_template.get("keys", [])} if "keys" in step_template else {},
                requires_ui_scan=step_template.get("requires_ui", False),
                verification_condition=verification
            )
            self.step_counter += 1
            steps.append(step)
            
        return steps
    
    def _replace_placeholders(self, text: str, intent: Dict) -> str:
        """Replace {placeholder} with intent values."""
        replacements = {
            "{app}": intent.get("target_app", ""),
            "{source_app}": intent.get("source_app", ""),
            "{text}": intent.get("parameters", {}).get("text", ""),
            "{query}": intent.get("parameters", {}).get("query", ""),
            "{url}": intent.get("parameters", {}).get("destination", ""),
            "{name}": intent.get("parameters", {}).get("name", ""),
            "{location}": intent.get("destination", ""),
            "{target_app}": intent.get("target_app", ""),
        }
        
        result = text
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, str(value) if value else "")
        return result
    
    def _build_custom_plan(self, intent: Dict) -> List[ExecutionStep]:
        """Build plan for intents without templates."""
        steps = []
        action = intent.get("action", "unknown")
        
        # Start with app opening if target_app specified
        if intent.get("target_app"):
            steps.append(ExecutionStep(
                step_id=f"step_{self.step_counter}",
                step_number=len(steps),
                action="open_app",
                target=intent["target_app"],
                verification_condition=f"window_exists:{intent['target_app']}"
            ))
            self.step_counter += 1
            
            steps.append(ExecutionStep(
                step_id=f"step_{self.step_counter}",
                step_number=len(steps),
                action="wait",
                target="1",
                verification_condition="app_ready"
            ))
            self.step_counter += 1
        
        # Add UI scan for complex actions
        if not intent.get("is_deterministic", True):
            steps.append(ExecutionStep(
                step_id=f"step_{self.step_counter}",
                step_number=len(steps),
                action="ui_scan",
                target="current_window",
                requires_ui_scan=True,
                verification_condition="ui_tree_captured"
            ))
            self.step_counter += 1
        
        # Add main action
        if action != "open" and action != "close":
            steps.append(ExecutionStep(
                step_id=f"step_{self.step_counter}",
                step_number=len(steps),
                action=action,
                target=intent.get("object_type", "element"),
                parameters={
                    "selector": intent.get("object_selector"),
                    "destination": intent.get("destination")
                },
                requires_ui_scan=True,
                verification_condition=f"{action}_completed"
            ))
            self.step_counter += 1
        
        return steps

    def _build_search_plan(self, intent: Dict) -> List[ExecutionStep]:
        """Build search plan with Strict Query Constraint."""
        query = intent.get("parameters", {}).get("query", "") or intent.get("target", "") or intent.get("object_selector", "")
        # Filter out placeholders
        if query in ["...", "None", ""]: query = None
        
        steps = []
        
        # 1. Open Browser
        steps.append(ExecutionStep(
            step_id=f"step_{self.step_counter}",
            step_number=len(steps),
            action="open_app",
            target="chrome",
            verification_condition="window_exists:chrome"
        ))
        self.step_counter += 1
        
        # 2. If Query exists -> Execute Search
        if query:
            steps.append(ExecutionStep(
                 step_id=f"step_{self.step_counter}", 
                 step_number=len(steps),
                 action="wait", target="1",
                 verification_condition="app_ready"
            ))
            self.step_counter += 1
            
            steps.append(ExecutionStep(
                 step_id=f"step_{self.step_counter}",
                 step_number=len(steps),
                 action="navigate", # Semantic action
                 target="google.com",
                 parameters={"query": query},
                 verification_condition=f"search_completed:{query}"
            ))
            self.step_counter += 1
            
        else:
            # 3. No Query -> Navigate Home & STOP (Wait State)
            steps.append(ExecutionStep(
                step_id=f"step_{self.step_counter}",
                step_number=len(steps),
                action="navigate",
                target="https://www.google.com",
                verification_condition="page_loaded"
            ))
            self.step_counter += 1
            
            # Explicit Wait/Stop implied by end of plan without search actions
            print("[TaskPlanner] No query provided. Generating Open-Only plan.")
            
        return steps
    
    
    def replan_from_step(self, original_plan: ExecutionPlan, failed_step: int, 
                        error: str, ui_state: Dict) -> ExecutionPlan:
        """
        Create new plan starting from failed step.
        
        Args:
            original_plan: The plan that failed
            failed_step: Step number that failed
            error: Error message
            ui_state: Current UI state for context
            
        Returns:
            New ExecutionPlan starting from failure point
        """
        remaining_steps = []
        
        # Get steps after failure point
        for step in original_plan.steps[failed_step:]:
            # Create new step with retry info
            new_step = ExecutionStep(
                step_id=f"retry_{step.step_id}",
                step_number=len(remaining_steps),
                action=step.action,
                target=step.target,
                parameters=step.parameters,
                requires_ui_scan=True,  # Always rescan after failure
                verification_condition=step.verification_condition,
                fallback_action=step.action  # Could be different fallback
            )
            remaining_steps.append(new_step)
        
        new_plan = ExecutionPlan(
            plan_id=f"replan_{original_plan.plan_id}",
            intent_id=original_plan.intent_id,
            steps=remaining_steps,
            total_steps=len(remaining_steps)
        )
        
        print(f"DEBUG TaskPlanner: Replanned from step {failed_step}, {len(remaining_steps)} steps remaining")
        return new_plan
