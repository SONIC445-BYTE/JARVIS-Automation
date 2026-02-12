"""
Intent Planner - Convert Natural Language to Action Sequence
==============================================================
Parses user intent and generates deterministic action plans.

Sprint 2: Autonomous Action
"""

import re
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ActionType(Enum):
    """Atomic action types."""
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    WAIT = "wait"
    NAVIGATE = "navigate"
    SEARCH = "search"
    SELECT = "select"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SCREENSHOT = "screenshot"


@dataclass
class ActionStep:
    """Single atomic action in a plan."""
    step_id: int
    action_type: ActionType
    target: Optional[str] = None          # App name or element
    selector: Optional[Dict] = None       # Element selector
    params: Dict = field(default_factory=dict)
    verify_selector: Optional[Dict] = None  # Post-action verification
    timeout: float = 10.0
    retry_count: int = 2
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['action_type'] = self.action_type.value
        return d

class ExecutionStep(ActionStep):
    """Compatibility class for legacy adapters."""
    def __init__(self, action: str = None, target: str = None, parameters: Dict = None, **kwargs):
        # Convert action string to ActionType
        a_type = ActionType.CLICK
        try:
            a_type = ActionType(action)
        except:
            # Fallback for mismatched names
            mapping = {"navigate": ActionType.NAVIGATE, "type": ActionType.TYPE, "click": ActionType.CLICK}
            a_type = mapping.get(action, ActionType.CLICK)
            
        super().__init__(
            step_id=kwargs.get("step_id", 0),
            action_type=a_type,
            target=target,
            params=parameters if parameters is not None else kwargs.get("params", {}),
            **{k: v for k, v in kwargs.items() if k not in ["step_id", "params"]}
        )


@dataclass
class ActionPlan:
    """Complete execution plan for an intent."""
    plan_id: str
    intent_text: str
    target_app: Optional[str] = None
    steps: List[ActionStep] = field(default_factory=list)
    risk_level: str = "standard"
    confirm_required: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "intent_text": self.intent_text,
            "target_app": self.target_app,
            "steps": [s.to_dict() for s in self.steps],
            "risk_level": self.risk_level,
            "confirm_required": self.confirm_required
        }


class IntentPlanner:
    """
    Converts natural language intents to structured action plans.
    
    Uses pattern matching + templates for deterministic planning.
    """
    
    # App name mappings
    APP_ALIASES = {
        "notepad": "notepad.exe",
        "browser": "chrome.exe",
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "file explorer": "explorer.exe",
        "explorer": "explorer.exe",
        "terminal": "cmd.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "settings": "ms-settings:",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "whatsapp": "WhatsApp",
        "spotify": "Spotify",
        "vscode": "Code.exe",
        "code": "Code.exe",
    }
    
    # Intent patterns with extractors
    INTENT_PATTERNS = [
        # Open app
        (r"open\s+(?:the\s+)?(.+?)(?:\s+app)?$", "open_app"),
        # Close app
        (r"close\s+(?:the\s+)?(.+?)(?:\s+app)?$", "close_app"),
        # Type text
        (r"type\s+['\"]?(.+?)['\"]?(?:\s+in\s+(.+))?$", "type_text"),
        # Search
        (r"search\s+(?:for\s+)?['\"]?(.+?)['\"]?(?:\s+(?:on|in)\s+(.+))?$", "search"),
        # Navigate
        (r"go\s+to\s+(.+)$", "navigate"),
        # Click
        (r"click\s+(?:on\s+)?(?:the\s+)?(.+)$", "click"),
        # Scroll
        (r"scroll\s+(up|down)(?:\s+(?:in\s+)?(.+))?$", "scroll"),
        # Multi-step: open and type
        (r"open\s+(.+?)\s+and\s+type\s+['\"]?(.+?)['\"]?$", "open_and_type"),
        # Multi-step: open and search
        (r"open\s+(.+?)\s+and\s+search\s+(?:for\s+)?['\"]?(.+?)['\"]?$", "open_and_search"),
        # Upload
        (r"upload\s+(?:the\s+)?(.+?)\s+(?:to|on)\s+(.+)$", "upload"),
        # Download
        (r"download\s+(?:the\s+)?(.+?)(?:\s+from\s+(.+))?$", "download"),
    ]
    
    def __init__(self):
        self._plan_counter = 0
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), action) 
            for p, action in self.INTENT_PATTERNS
        ]
    
    def plan(self, intent_text: str) -> Optional[ActionPlan]:
        """
        Convert intent text to action plan.
        
        Args:
            intent_text: Natural language command
            
        Returns:
            ActionPlan or None if not parseable
        """
        intent_text = intent_text.strip().lower()
        
        for pattern, action_type in self._compiled_patterns:
            match = pattern.match(intent_text)
            if match:
                return self._build_plan(action_type, match.groups(), intent_text)
        
        # Fallback: try simple parsing
        return self._fallback_plan(intent_text)
    
    def _build_plan(self, action_type: str, groups: tuple, intent: str) -> ActionPlan:
        """Build plan from matched pattern."""
        self._plan_counter += 1
        plan_id = f"plan_{self._plan_counter}"
        
        if action_type == "open_app":
            app_name = groups[0].strip()
            return self._plan_open_app(plan_id, intent, app_name)
            
        elif action_type == "close_app":
            app_name = groups[0].strip()
            return self._plan_close_app(plan_id, intent, app_name)
            
        elif action_type == "type_text":
            text = groups[0]
            target = groups[1] if len(groups) > 1 else None
            return self._plan_type_text(plan_id, intent, text, target)
            
        elif action_type == "search":
            query = groups[0]
            app = groups[1] if len(groups) > 1 else "chrome"
            return self._plan_search(plan_id, intent, query, app)
            
        elif action_type == "navigate":
            destination = groups[0]
            return self._plan_navigate(plan_id, intent, destination)
            
        elif action_type == "click":
            target = groups[0]
            return self._plan_click(plan_id, intent, target)
            
        elif action_type == "scroll":
            direction = groups[0]
            target = groups[1] if len(groups) > 1 else None
            return self._plan_scroll(plan_id, intent, direction, target)
            
        elif action_type == "open_and_type":
            app = groups[0]
            text = groups[1]
            return self._plan_open_and_type(plan_id, intent, app, text)
            
        elif action_type == "open_and_search":
            app = groups[0]
            query = groups[1]
            return self._plan_open_and_search(plan_id, intent, app, query)
            
        elif action_type == "upload":
            file = groups[0]
            destination = groups[1]
            return self._plan_upload(plan_id, intent, file, destination)
            
        elif action_type == "download":
            item = groups[0]
            source = groups[1] if len(groups) > 1 else None
            return self._plan_download(plan_id, intent, item, source)
        
        # Fallback
        return self._fallback_plan(intent)
    
    def _get_app_executable(self, app_name: str) -> str:
        """Resolve app name to executable."""
        return self.APP_ALIASES.get(app_name.lower(), app_name)
    
    # ============ Plan Builders ============
    
    def _plan_open_app(self, plan_id: str, intent: str, app: str) -> ActionPlan:
        exe = self._get_app_executable(app)
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            target_app=exe,
            steps=[
                ActionStep(
                    step_id=1,
                    action_type=ActionType.OPEN_APP,
                    target=exe,
                    params={"app_name": app},
                    verify_selector={"window_title_contains": app}
                )
            ]
        )
    
    def _plan_close_app(self, plan_id: str, intent: str, app: str) -> ActionPlan:
        exe = self._get_app_executable(app)
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            target_app=exe,
            steps=[
                ActionStep(
                    step_id=1,
                    action_type=ActionType.CLOSE_APP,
                    target=exe,
                    params={"app_name": app}
                )
            ]
        )
    
    def _plan_type_text(self, plan_id: str, intent: str, text: str, target: Optional[str]) -> ActionPlan:
        steps = []
        if target:
            steps.append(ActionStep(
                step_id=1,
                action_type=ActionType.CLICK,
                selector={"label": target}
            ))
        steps.append(ActionStep(
            step_id=len(steps) + 1,
            action_type=ActionType.TYPE,
            params={"text": text}
        ))
        return ActionPlan(plan_id=plan_id, intent_text=intent, steps=steps)
    
    def _plan_search(self, plan_id: str, intent: str, query: str, app: str) -> ActionPlan:
        exe = self._get_app_executable(app)
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            target_app=exe,
            steps=[
                ActionStep(step_id=1, action_type=ActionType.OPEN_APP, target=exe),
                ActionStep(step_id=2, action_type=ActionType.WAIT, params={"seconds": 1}),
                ActionStep(step_id=3, action_type=ActionType.SEARCH, params={"query": query})
            ]
        )
    
    def _plan_navigate(self, plan_id: str, intent: str, destination: str) -> ActionPlan:
        # Handle URLs
        if not destination.startswith(("http://", "https://")):
            if "." in destination:
                destination = f"https://{destination}"
        
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            steps=[
                ActionStep(
                    step_id=1,
                    action_type=ActionType.NAVIGATE,
                    params={"url": destination}
                )
            ]
        )
    
    def _plan_click(self, plan_id: str, intent: str, target: str) -> ActionPlan:
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            steps=[
                ActionStep(
                    step_id=1,
                    action_type=ActionType.CLICK,
                    selector={"label": target, "fuzzy": True}
                )
            ]
        )
    
    def _plan_scroll(self, plan_id: str, intent: str, direction: str, target: Optional[str]) -> ActionPlan:
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            steps=[
                ActionStep(
                    step_id=1,
                    action_type=ActionType.SCROLL,
                    params={"direction": direction, "amount": 3}
                )
            ]
        )
    
    def _plan_open_and_type(self, plan_id: str, intent: str, app: str, text: str) -> ActionPlan:
        exe = self._get_app_executable(app)
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            target_app=exe,
            steps=[
                ActionStep(step_id=1, action_type=ActionType.OPEN_APP, target=exe),
                ActionStep(step_id=2, action_type=ActionType.WAIT, params={"seconds": 1}),
                ActionStep(step_id=3, action_type=ActionType.TYPE, params={"text": text})
            ]
        )
    
    def _plan_open_and_search(self, plan_id: str, intent: str, app: str, query: str) -> ActionPlan:
        exe = self._get_app_executable(app)
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            target_app=exe,
            steps=[
                ActionStep(step_id=1, action_type=ActionType.OPEN_APP, target=exe),
                ActionStep(step_id=2, action_type=ActionType.WAIT, params={"seconds": 2}),
                ActionStep(step_id=3, action_type=ActionType.SEARCH, params={"query": query})
            ]
        )
    
    def _plan_upload(self, plan_id: str, intent: str, file: str, destination: str) -> ActionPlan:
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            risk_level="destructive",
            confirm_required=True,
            steps=[
                ActionStep(step_id=1, action_type=ActionType.UPLOAD, 
                          params={"file": file, "destination": destination})
            ]
        )
    
    def _plan_download(self, plan_id: str, intent: str, item: str, source: Optional[str]) -> ActionPlan:
        return ActionPlan(
            plan_id=plan_id,
            intent_text=intent,
            steps=[
                ActionStep(step_id=1, action_type=ActionType.DOWNLOAD,
                          params={"item": item, "source": source})
            ]
        )
    
    def _fallback_plan(self, intent: str) -> ActionPlan:
        """Fallback for unrecognized intents."""
        self._plan_counter += 1
        return ActionPlan(
            plan_id=f"plan_{self._plan_counter}",
            intent_text=intent,
            risk_level="unknown",
            steps=[]
        )


def test_intent_planner():
    """Test intent planning."""
    planner = IntentPlanner()
    
    tests = [
        "open notepad",
        "close chrome",
        "type hello world",
        "search for python tutorials on youtube",
        "go to google.com",
        "open notepad and type hello world",
        "scroll down",
        "click on the submit button",
    ]
    
    print("Intent Planner Test")
    print("=" * 50)
    
    for intent in tests:
        plan = planner.plan(intent)
        print(f"\nIntent: '{intent}'")
        print(f"  Plan ID: {plan.plan_id}")
        print(f"  Target App: {plan.target_app}")
        print(f"  Steps: {len(plan.steps)}")
        for step in plan.steps:
            print(f"    {step.step_id}. {step.action_type.value} -> {step.target or step.params}")


if __name__ == "__main__":
    test_intent_planner()
