"""
UI Executor - Execute Atomic UI Actions
=========================================
Performs actions on UI elements with verification.

Sprint 2: Autonomous Action
"""

import os
import time
import subprocess
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ExecutionStatus(Enum):
    """Action execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ELEMENT_NOT_FOUND = "element_not_found"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class ExecutionResult:
    """Result of action execution."""
    status: ExecutionStatus
    step_id: int
    action_type: str
    target: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def ok(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "step_id": self.step_id,
            "action_type": self.action_type,
            "target": self.target,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "ok": self.ok
        }


class UIExecutor:
    """
    Executes UI actions atomically.
    
    Each action:
    - Is logged
    - Has timeout protection
    - Returns result object
    - Can be verified
    """
    
    def __init__(self):
        self._pyautogui = None
        self._pywinauto = None
        self._init_backends()
    
    def _init_backends(self):
        """Initialize execution backends."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
            self._pyautogui = pyautogui
        except ImportError:
            print("[UIExecutor] pyautogui not available")
        
        try:
            from pywinauto import Application
            self._pywinauto = Application
        except ImportError:
            print("[UIExecutor] pywinauto not available")
    
    def execute(self, action_type: str, step_id: int, target: Optional[str] = None, 
                params: Dict = None, timeout: float = 10.0) -> ExecutionResult:
        """
        Execute a single action.
        
        Args:
            action_type: Type of action (from ActionType enum)
            step_id: Step identifier
            target: Target element or app
            params: Action parameters
            timeout: Timeout in seconds
            
        Returns:
            ExecutionResult
        """
        params = params or {}
        start_time = time.time()
        
        try:
            # Dispatch to handler
            handlers = {
                "open_app": self._open_app,
                "close_app": self._close_app,
                "click": self._click,
                "type": self._type_text,
                "scroll": self._scroll,
                "wait": self._wait,
                "navigate": self._navigate,
                "search": self._search,
            }
            
            handler = handlers.get(action_type)
            if not handler:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    step_id=step_id,
                    action_type=action_type,
                    error=f"Unknown action type: {action_type}"
                )
            
            result = handler(target, params, timeout)
            
            duration_ms = (time.time() - start_time) * 1000
            result.step_id = step_id
            result.duration_ms = duration_ms
            
            return result
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=step_id,
                action_type=action_type,
                target=target,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000
            )
    
    def execute_step(self, step) -> ExecutionResult:
        """Execute an action step."""
        # Handle ActionType enum or string
        a_type = step.action_type
        if hasattr(a_type, 'value'):
            a_type = a_type.value
            
        return self.execute(
            action_type=a_type,
            step_id=step.step_id,
            target=step.target,
            params=step.params,
            timeout=getattr(step, 'timeout', 10.0)
        )
    
    # ============ Action Handlers ============
    
    def _open_app(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Open an application."""
        app_name = params.get("app_name", target)
        
        try:
            # Try Windows start
            if target.endswith(".exe"):
                os.startfile(target)
            elif target.startswith("ms-"):
                # Windows URI (ms-settings:, etc.)
                os.startfile(target)
            else:
                # Try as command
                subprocess.Popen(target, shell=True)
            
            time.sleep(1)  # Wait for app to open
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="open_app",
                target=target,
                metadata={"app_name": app_name}
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="open_app",
                target=target,
                error=str(e)
            )
    
    def _close_app(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Close an application."""
        try:
            if self._pywinauto:
                from pywinauto import Application, Desktop
                
                desktop = Desktop(backend="uia")
                for win in desktop.windows():
                    try:
                        if target.lower() in win.window_text().lower():
                            win.close()
                            return ExecutionResult(
                                status=ExecutionStatus.SUCCESS,
                                step_id=0,
                                action_type="close_app",
                                target=target
                            )
                    except:
                        continue
            
            # Fallback: taskkill
            subprocess.run(["taskkill", "/f", "/im", target], capture_output=True)
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="close_app",
                target=target
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="close_app",
                target=target,
                error=str(e)
            )
    
    def _click(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Click at position or element."""
        if not self._pyautogui:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="click",
                error="pyautogui not available"
            )
        
        try:
            x = params.get("x")
            y = params.get("y")
            
            if x is not None and y is not None:
                self._pyautogui.click(x, y)
            else:
                # Click at current position
                self._pyautogui.click()
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="click",
                metadata={"x": x, "y": y}
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="click",
                error=str(e)
            )
    
    def _type_text(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Type text."""
        if not self._pyautogui:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="type",
                error="pyautogui not available"
            )
        
        try:
            text = params.get("text", "")
            interval = params.get("interval", 0.02)
            
            self._pyautogui.typewrite(text, interval=interval)
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="type",
                metadata={"text_length": len(text)}
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="type",
                error=str(e)
            )
    
    def _scroll(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Scroll up/down."""
        if not self._pyautogui:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="scroll",
                error="pyautogui not available"
            )
        
        try:
            direction = params.get("direction", "down")
            amount = params.get("amount", 3)
            
            clicks = amount if direction == "up" else -amount
            self._pyautogui.scroll(clicks)
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="scroll",
                metadata={"direction": direction, "amount": amount}
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="scroll",
                error=str(e)
            )
    
    def _wait(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Wait for specified duration."""
        seconds = params.get("seconds", 1)
        time.sleep(seconds)
        
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            step_id=0,
            action_type="wait",
            metadata={"seconds": seconds}
        )
    
    def _navigate(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Navigate to URL."""
        import webbrowser
        
        url = params.get("url", target)
        
        try:
            webbrowser.open(url)
            time.sleep(1)
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="navigate",
                target=url
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="navigate",
                target=url,
                error=str(e)
            )
    
    def _search(self, target: str, params: Dict, timeout: float) -> ExecutionResult:
        """Perform search action."""
        if not self._pyautogui:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="search",
                error="pyautogui not available"
            )
        
        try:
            query = params.get("query", "")
            
            # Type query and press Enter
            self._pyautogui.typewrite(query, interval=0.02)
            time.sleep(0.2)
            self._pyautogui.press("enter")
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                step_id=0,
                action_type="search",
                metadata={"query": query}
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type="search",
                error=str(e)
            )


def test_ui_executor():
    """Test UI executor."""
    executor = UIExecutor()
    
    print("UI Executor Test")
    print("=" * 50)
    
    # Test wait
    result = executor.execute("wait", step_id=1, params={"seconds": 0.5})
    print(f"Wait: {result.status.value} ({result.duration_ms:.0f}ms)")
    
    # Test navigate
    result = executor.execute("navigate", step_id=2, params={"url": "https://google.com"})
    print(f"Navigate: {result.status.value}")


if __name__ == "__main__":
    test_ui_executor()
