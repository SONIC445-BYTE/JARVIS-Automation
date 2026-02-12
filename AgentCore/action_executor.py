"""
Action Executor - Execute UI Actions
=====================================
Performs actions based on UI perception.

ODAV Role: "Act" layer - executes decided actions.

Every action is:
- Logged
- Explainable (references element or context)
- Recoverable
"""

import time
import subprocess
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import pyautogui

# Configure pyautogui safety
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    WAIT = "wait"
    MOVE = "move"
    SEND = "send"
    SEARCH = "search"
    NAVIGATE = "navigate"


@dataclass
class ActionResult:
    """Result of an executed action."""
    success: bool
    action_type: str
    target: str
    coordinates: Optional[Tuple[int, int]]
    duration_ms: int
    error: Optional[str] = None
    degraded: bool = False  # True if used fallback method
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActionExecutor:
    """
    Executes UI actions with logging and explanation.
    
    Golden Rule: Never execute a click you cannot explain.
    Every action references an element or has clear context.
    """
    
    def __init__(self):
        self.action_log: list = []
        
    def execute(self, action: Dict[str, Any]) -> ActionResult:
        """
        Execute an action from the task plan.
        
        Args:
            action: Dict with 'type' and action-specific params
            
        Returns:
            ActionResult with success status
        """
        action_type = action.get("type", "").lower()
        start_time = time.time()
        
        try:
            if action_type == "click":
                result = self.click(
                    action.get("x"), 
                    action.get("y"),
                    action.get("element_name", "unknown")
                )
            elif action_type == "double_click":
                result = self.double_click(action.get("x"), action.get("y"))
            elif action_type == "right_click":
                result = self.right_click(action.get("x"), action.get("y"))
            elif action_type == "type":
                result = self.type_text(action.get("text", ""))
            elif action_type == "hotkey":
                result = self.hotkey(*action.get("keys", []))
            elif action_type == "scroll":
                result = self.scroll(
                    action.get("direction", "down"),
                    action.get("amount", 3)
                )
            elif action_type == "open_app":
                result = self.open_app(action.get("app_name", ""))
            elif action_type == "close_app":
                result = self.close_app(action.get("app_name"))
            elif action_type == "wait":
                result = self.wait(action.get("seconds", 1))
            elif action_type == "move":
                result = self.move_mouse(action.get("x"), action.get("y"))
            elif action_type == "send":
                result = self.send_input()
            elif action_type == "search":
                result = self.search(action.get("query", ""))
            elif action_type == "navigate":
                result = self.navigate(action.get("url", ""))
            else:
                result = ActionResult(
                    success=False,
                    action_type=action_type,
                    target="unknown",
                    coordinates=None,
                    duration_ms=0,
                    error=f"Unknown action type: {action_type}"
                )
                
            result.duration_ms = int((time.time() - start_time) * 1000)
            self._log_action(result)
            return result
            
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=action_type,
                target=str(action),
                coordinates=None,
                duration_ms=int((time.time() - start_time) * 1000),
                error=str(e)
            )
            self._log_action(result)
            return result
    
    def click(self, x: int, y: int, element_name: str = "unknown") -> ActionResult:
        """
        Click at coordinates.
        
        Args:
            x, y: Coordinates to click
            element_name: Name of element being clicked (for logging)
        """
        print(f"DEBUG ActionExecutor: Click at ({x}, {y}) - {element_name}")
        pyautogui.click(x, y)
        return ActionResult(
            success=True,
            action_type="click",
            target=element_name,
            coordinates=(x, y),
            duration_ms=0
        )
    
    def double_click(self, x: int, y: int) -> ActionResult:
        """Double-click at coordinates."""
        print(f"DEBUG ActionExecutor: Double-click at ({x}, {y})")
        pyautogui.doubleClick(x, y)
        return ActionResult(
            success=True,
            action_type="double_click",
            target=f"({x}, {y})",
            coordinates=(x, y),
            duration_ms=0
        )
    
    def right_click(self, x: int, y: int) -> ActionResult:
        """Right-click at coordinates."""
        print(f"DEBUG ActionExecutor: Right-click at ({x}, {y})")
        pyautogui.rightClick(x, y)
        return ActionResult(
            success=True,
            action_type="right_click",
            target=f"({x}, {y})",
            coordinates=(x, y),
            duration_ms=0
        )
    
    def type_text(self, text: str, interval: float = 0.02) -> ActionResult:
        """
        Type text with keyboard.
        
        Args:
            text: Text to type
            interval: Delay between keystrokes
        """
        print(f"DEBUG ActionExecutor: Typing '{text[:50]}...'")
        pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.write(text)
        return ActionResult(
            success=True,
            action_type="type",
            target=text[:50],
            coordinates=None,
            duration_ms=0
        )
    
    def hotkey(self, *keys) -> ActionResult:
        """
        Press hotkey combination.
        
        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')
        """
        print(f"DEBUG ActionExecutor: Hotkey {'+'.join(keys)}")
        pyautogui.hotkey(*keys)
        return ActionResult(
            success=True,
            action_type="hotkey",
            target='+'.join(keys),
            coordinates=None,
            duration_ms=0
        )
    
    def scroll(self, direction: str, amount: int = 3) -> ActionResult:
        """
        Scroll in direction.
        
        Args:
            direction: 'up' or 'down'
            amount: Number of scroll units
        """
        scroll_amount = amount if direction == "up" else -amount
        print(f"DEBUG ActionExecutor: Scroll {direction} by {amount}")
        pyautogui.scroll(scroll_amount)
        return ActionResult(
            success=True,
            action_type="scroll",
            target=direction,
            coordinates=None,
            duration_ms=0
        )
    
    def open_app(self, app_name: str) -> ActionResult:
        """
        Open an application.
        
        Uses Windows Start menu search as reliable method.
        """
        print(f"DEBUG ActionExecutor: Opening app '{app_name}'")
        
        # Method 1: Try direct execution for known apps
        direct_apps = {
            "notepad": "notepad.exe",
            "explorer": "explorer.exe",
            "chrome": "start chrome",
            "firefox": "start firefox",
            "edge": "start msedge",
            "vscode": "code",
        }
        
        app_lower = app_name.lower()
        if app_lower in direct_apps:
            try:
                subprocess.Popen(direct_apps[app_lower], shell=True)
                time.sleep(0.5)
                return ActionResult(
                    success=True,
                    action_type="open_app",
                    target=app_name,
                    coordinates=None,
                    duration_ms=0
                )
            except:
                pass
        
        # Method 2: Use Windows Start menu search
        pyautogui.press("win")
        time.sleep(0.3)
        pyautogui.typewrite(app_name, interval=0.05)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.5)
        
        return ActionResult(
            success=True,
            action_type="open_app",
            target=app_name,
            coordinates=None,
            duration_ms=0,
            degraded=True  # Used search method
        )
    
    def close_app(self, app_name: Optional[str] = None) -> ActionResult:
        """
        Close an application or current window.
        
        Args:
            app_name: Specific app to close, or None for current window
        """
        if app_name:
            print(f"DEBUG ActionExecutor: Closing app '{app_name}'")
            # Try taskkill for specific app
            process_map = {
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "edge": "msedge.exe",
                "notepad": "notepad.exe",
                "vscode": "Code.exe",
            }
            process = process_map.get(app_name.lower(), f"{app_name}.exe")
            try:
                subprocess.run(["taskkill", "/f", "/im", process], 
                              capture_output=True, check=True)
                return ActionResult(
                    success=True,
                    action_type="close_app",
                    target=app_name,
                    coordinates=None,
                    duration_ms=0
                )
            except:
                # Fallback to Alt+F4
                pyautogui.hotkey('alt', 'f4')
                return ActionResult(
                    success=True,
                    action_type="close_app",
                    target=app_name,
                    coordinates=None,
                    duration_ms=0,
                    degraded=True
                )
        else:
            # Close current window
            print("DEBUG ActionExecutor: Closing current window (Alt+F4)")
            pyautogui.hotkey('alt', 'f4')
            return ActionResult(
                success=True,
                action_type="close_app",
                target="current_window",
                coordinates=None,
                duration_ms=0
            )
    
    def wait(self, seconds: float) -> ActionResult:
        """Wait for specified duration."""
        print(f"DEBUG ActionExecutor: Waiting {seconds}s")
        time.sleep(seconds)
        return ActionResult(
            success=True,
            action_type="wait",
            target=f"{seconds}s",
            coordinates=None,
            duration_ms=int(seconds * 1000)
        )
    
    def move_mouse(self, x: int, y: int) -> ActionResult:
        """Move mouse to coordinates."""
        print(f"DEBUG ActionExecutor: Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.2)
        return ActionResult(
            success=True,
            action_type="move",
            target=f"({x}, {y})",
            coordinates=(x, y),
            duration_ms=0
        )
    
    def send_input(self) -> ActionResult:
        """Send/submit input (usually by pressing Enter)."""
        print("DEBUG ActionExecutor: Sending input (Enter)")
        pyautogui.press("enter")
        return ActionResult(
            success=True,
            action_type="send",
            target="enter_key",
            coordinates=None,
            duration_ms=0
        )

    def search(self, query: str) -> ActionResult:
        """
        Execute search (Ctrl+L -> Type -> Enter).
        """
        print(f"DEBUG ActionExecutor: Searching for '{query}'")
        # 1. Focus address bar
        self.hotkey('ctrl', 'l')
        time.sleep(0.2)
        # 2. Type query
        self.type_text(query)
        time.sleep(0.2)
        # 3. Enter
        self.send_input()
        
        return ActionResult(
            success=True,
            action_type="search",
            target=query,
            coordinates=None,
            duration_ms=0
        )

    def navigate(self, url: str) -> ActionResult:
        """
        Navigate to URL (Ctrl+L -> Type -> Enter).
        """
        print(f"DEBUG ActionExecutor: Navigating to '{url}'")
        # 1. Focus address bar
        self.hotkey('ctrl', 'l')
        time.sleep(0.2)
        # 2. Type URL
        self.type_text(url)
        time.sleep(0.2)
        # 3. Enter
        self.send_input()
        
        return ActionResult(
            success=True,
            action_type="navigate",
            target=url,
            coordinates=None,
            duration_ms=0
        )

    def _log_action(self, result: ActionResult):
        """Log action for history."""
        self.action_log.append(result.to_dict())
        
    def get_action_history(self) -> list:
        """Get history of executed actions."""
        return self.action_log.copy()
    
    def clear_history(self):
        """Clear action history."""
        self.action_log.clear()
