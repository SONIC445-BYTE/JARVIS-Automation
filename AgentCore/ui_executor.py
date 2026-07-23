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
    # Phase 2g: a CAPTCHA/login-wall was detected -- distinct from
    # FAILED. A block isn't a failure, it's a pause: the caller should
    # surface the reason and wait for a human to clear it, then retry
    # the same command, not report an error and give up.
    BLOCKED = "blocked"


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
    
    def __init__(self, adapter_dry_run: bool = False):
        self._pyautogui = None
        self._pywinauto = None
        self._adapters = None
        self._adapter_dry_run = adapter_dry_run
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
    
    # ============ Adapter-routed execution (Phase 2a) ============

    def execute_intent(self, intent) -> ExecutionResult:
        """
        Execute a resolved Intent (see AgentCore/command_router.py) by
        dispatching to the matching adapter's declared method. Falls back
        to the raw subprocess/os.startfile path only for open_app/
        close_app when no adapter is registered for intent.adapter --
        send_message/read_unread have no legacy fallback, since nothing
        implemented them before this.
        """
        start_time = time.time()

        # 5th instance of the router-hands-adapters-an-unclean-value bug
        # family: CommandRouter.resolve() sets this when an action needs
        # a genuine dictated message but none was extractable (see
        # daemon/intent_parser.py's Intent.message_required_but_missing
        # docstring). Checked here, before any adapter is touched, so
        # this is a single central gate rather than a per-adapter patch,
        # and so no adapter ever gets called with the empty/missing
        # message this flag exists to prevent silently masking.
        if getattr(intent, "message_required_but_missing", False):
            who = f" to {intent.target}" if intent.target else ""
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                step_id=0,
                action_type=intent.action,
                target=intent.target,
                error=f"I didn't catch what you wanted to say{who} -- please include it, e.g. '...saying <message>'.",
                duration_ms=(time.time() - start_time) * 1000,
            )

        adapter = self._get_adapter(intent.adapter)

        if adapter is not None and adapter.supports(intent.action):
            try:
                value = self._invoke_adapter_action(adapter, intent)
                # read_unread returning an empty list is a normal outcome
                # (no unread messages), not a failure.
                ok = True if intent.action == "read_unread" else bool(value)
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS if ok else ExecutionStatus.FAILED,
                    step_id=0,
                    action_type=intent.action,
                    target=intent.target,
                    duration_ms=(time.time() - start_time) * 1000,
                    metadata={"adapter": intent.adapter, "value": value},
                )
            except Exception as e:
                # Phase 2g: a CAPTCHA/login-wall is a pause, not a
                # failure -- checked by type, not string-matched, so a
                # browser adapter's BlockedError is never confused with
                # a genuine error. platform_adapters.browser_automation
                # is imported lazily here (not at module load) for the
                # same reason element_finder.py imports UIScanner
                # lazily: most adapters never need it, and Playwright
                # shouldn't become a load-time dependency for the ones
                # that don't.
                try:
                    from platform_adapters.browser_automation import BlockedError
                    is_blocked = isinstance(e, BlockedError)
                except ImportError:
                    is_blocked = False

                if is_blocked:
                    return ExecutionResult(
                        status=ExecutionStatus.BLOCKED,
                        step_id=0,
                        action_type=intent.action,
                        target=intent.target,
                        error=e.reason,
                        duration_ms=(time.time() - start_time) * 1000,
                    )
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    step_id=0,
                    action_type=intent.action,
                    target=intent.target,
                    error=str(e),
                    duration_ms=(time.time() - start_time) * 1000,
                )

        # No adapter for this platform -- legacy fallback exists only for
        # open_app/close_app (the two actions UIExecutor already supported
        # pre-Phase-2).
        if intent.action == "open_app":
            return self._open_app(intent.target, {}, 10.0)
        if intent.action == "close_app":
            return self._close_app(intent.target, {}, 10.0)

        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            step_id=0,
            action_type=intent.action,
            target=intent.target,
            error=f"No adapter registered for '{intent.adapter}' and no legacy fallback for '{intent.action}'",
            duration_ms=(time.time() - start_time) * 1000,
        )

    def _get_adapter(self, adapter_key: str):
        if self._adapters is None:
            self._adapters = self._build_adapter_registry()
        return self._adapters.get(adapter_key)

    def _build_adapter_registry(self) -> Dict[str, Any]:
        try:
            from platform_adapters.registry import create_default_adapters
            from daemon.logging_utils import ActionLogger
            from pathlib import Path

            logger = ActionLogger(Path("logs/jarvis_actions.log"))
            return create_default_adapters(logger=logger, dry_run=self._adapter_dry_run)
        except ImportError as e:
            print(f"[UIExecutor] Adapter registry unavailable: {e}")
            return {}

    @staticmethod
    def _invoke_adapter_action(adapter, intent):
        if intent.action == "open_app":
            return adapter.open_app()
        if intent.action == "close_app":
            return adapter.close_app()
        if intent.action == "send_message":
            return adapter.send_message(intent.target, intent.message)
        if intent.action == "read_unread":
            return adapter.read_unread()
        # Future platform-specific actions (e.g. Netflix play/pause, or
        # Phase 2d's calculate/new_tab/etc.): the convention is a method
        # on the adapter named exactly after ActionSpec.name, called with
        # (target, message) -- adapters that don't need either just
        # declare them as unused/defaulted parameters.
        method = getattr(adapter, intent.action, None)
        if method is None:
            raise AttributeError(f"Adapter for '{intent.adapter}' has no method '{intent.action}'")
        return method(intent.target, intent.message)

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
