"""
Mode Manager - Sleep ↔ Active State Transitions
=================================================
Controls JARVIS operational modes.

Now includes AudioArbiter for authoritative mic ownership.
"""

import time
import threading
from enum import Enum
from typing import Callable, Optional
from dataclasses import dataclass


class AudioArbiter:
    """
    Single authoritative owner of microphone access.
    
    BLOCKER FIX: Mode manager was polite (flags), not authoritative (locks).
    This class implements HARD LOCKS for mic access.
    
    Only one owner can access mic at a time.
    Prevents:
    - Simultaneous mic access
    - Audio frame competition
    - Phantom wake triggers
    """
    
    _instance = None
    _lock = threading.RLock()  # Re-entrant safe
    
    def __new__(cls):
        """Singleton pattern - only one arbiter."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_owner = None
            cls._instance._owner_lock = threading.RLock()
        return cls._instance
    
    def acquire(self, owner: str, timeout: float = 5.0) -> bool:
        """
        Acquire mic ownership.
        
        Args:
            owner: Identifier of requesting component
            timeout: Max seconds to wait for lock
            
        Returns:
            True if acquired, False if timeout
        """
        acquired = self._owner_lock.acquire(timeout=timeout)
        
        if acquired:
            with self._lock:
                self._current_owner = owner
                print(f"[AudioArbiter] Mic acquired by: {owner}")
            return True
        else:
            print(f"[AudioArbiter] Acquire timeout for: {owner}")
            return False
    
    def release(self, owner: str) -> bool:
        """
        Release mic ownership.
        
        Args:
            owner: Identifier of releasing component
            
        Returns:
            True if released, False if not owner
        """
        with self._lock:
            if self._current_owner != owner:
                print(f"[AudioArbiter] Release denied: {owner} is not owner (current: {self._current_owner})")
                return False
            
            self._current_owner = None
            print(f"[AudioArbiter] Mic released by: {owner}")
        
        try:
            self._owner_lock.release()
        except RuntimeError:
            pass  # Already released
        
        return True
    
    def force_release(self):
        """
        Force release mic (for mode transitions).
        
        Use sparingly - only for critical mode changes.
        """
        with self._lock:
            old_owner = self._current_owner
            self._current_owner = None
            print(f"[AudioArbiter] FORCE RELEASE from: {old_owner}")
        
        # Release lock if held
        try:
            self._owner_lock.release()
        except RuntimeError:
            pass
    
    def get_owner(self) -> Optional[str]:
        """Get current mic owner."""
        with self._lock:
            return self._current_owner
    
    def is_available(self) -> bool:
        """Check if mic is available."""
        with self._lock:
            return self._current_owner is None


class JarvisMode(Enum):
    """JARVIS operational modes."""
    BOOT = "boot"           # Starting up
    SLEEP = "sleep"         # Listening for wake word only
    WAKE = "wake"           # Wake word detected, acknowledging
    ACTIVE = "active"       # Full command processing
    SHUTDOWN = "shutdown"   # Shutting down


@dataclass
class ModeState:
    """Current mode state."""
    mode: JarvisMode
    entered_at: float
    wake_count: int = 0
    commands_processed: int = 0


class ModeManager:
    """
    Manages JARVIS mode transitions.
    
    State Machine:
    BOOT → SLEEP → WAKE → ACTIVE → SLEEP
                              ↓
                          SHUTDOWN
    """
    
    # Timeout to return to sleep (seconds)
    ACTIVE_TIMEOUT = 15.0
    
    # Commands that trigger shutdown
    SHUTDOWN_PHRASES = ["shut down", "shutdown", "stop listening", "go to sleep permanently"]
    
    # Commands that return to sleep
    SLEEP_PHRASES = ["go to sleep", "sleep", "that's all", "never mind", "stop"]
    
    def __init__(self):
        self.state = ModeState(mode=JarvisMode.BOOT, entered_at=time.time())
        self._lock = threading.Lock()
        self._timeout_timer: Optional[threading.Timer] = None
        self._on_mode_change: Optional[Callable[[JarvisMode, JarvisMode], None]] = None
        
    def set_callback(self, callback: Callable[[JarvisMode, JarvisMode], None]):
        """Set callback for mode changes. Called with (old_mode, new_mode)."""
        self._on_mode_change = callback
    
    def transition(self, new_mode: JarvisMode) -> bool:
        """
        Transition to new mode.
        
        Returns:
            True if transition successful
        """
        with self._lock:
            old_mode = self.state.mode
            
            # Validate transition
            valid_transitions = {
                JarvisMode.BOOT: [JarvisMode.SLEEP],
                JarvisMode.SLEEP: [JarvisMode.WAKE, JarvisMode.SHUTDOWN],
                JarvisMode.WAKE: [JarvisMode.ACTIVE, JarvisMode.SLEEP],
                JarvisMode.ACTIVE: [JarvisMode.SLEEP, JarvisMode.SHUTDOWN],
                JarvisMode.SHUTDOWN: [],
            }
            
            if new_mode not in valid_transitions.get(old_mode, []):
                if old_mode != new_mode:  # Ignore same-mode transitions
                    print(f"DEBUG ModeManager: Invalid transition {old_mode.value} → {new_mode.value}")
                return False
            
            # Cancel timeout timer
            if self._timeout_timer:
                self._timeout_timer.cancel()
                self._timeout_timer = None
            
            # Update state
            self.state.mode = new_mode
            self.state.entered_at = time.time()
            
            if new_mode == JarvisMode.WAKE:
                self.state.wake_count += 1
            
            print(f"DEBUG ModeManager: {old_mode.value} → {new_mode.value}")
            
            # Start timeout timer for active mode
            if new_mode == JarvisMode.ACTIVE:
                self._start_timeout()
            
            # Notify callback
            if self._on_mode_change:
                self._on_mode_change(old_mode, new_mode)
            
            return True
    
    def _start_timeout(self):
        """Start timer to return to sleep after timeout."""
        def timeout_callback():
            print("DEBUG ModeManager: Activity timeout, returning to sleep")
            self.transition(JarvisMode.SLEEP)
        
        self._timeout_timer = threading.Timer(self.ACTIVE_TIMEOUT, timeout_callback)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()
    
    def reset_timeout(self):
        """Reset activity timeout (call when command received)."""
        if self.state.mode == JarvisMode.ACTIVE:
            if self._timeout_timer:
                self._timeout_timer.cancel()
            self._start_timeout()
    
    def check_command(self, text: str) -> Optional[JarvisMode]:
        """
        Check if command triggers mode change.
        
        Returns:
            New mode to transition to, or None
        """
        text_lower = text.lower().strip()
        
        # Check shutdown phrases
        for phrase in self.SHUTDOWN_PHRASES:
            if phrase in text_lower:
                return JarvisMode.SHUTDOWN
        
        # Check sleep phrases
        for phrase in self.SLEEP_PHRASES:
            if phrase in text_lower:
                return JarvisMode.SLEEP
        
        return None
    
    def is_active(self) -> bool:
        """Check if in active command-processing mode."""
        return self.state.mode in [JarvisMode.WAKE, JarvisMode.ACTIVE]
    
    def is_sleeping(self) -> bool:
        """Check if in sleep mode."""
        return self.state.mode == JarvisMode.SLEEP
    
    def get_status(self) -> dict:
        """Get current status."""
        return {
            "mode": self.state.mode.value,
            "uptime": time.time() - self.state.entered_at,
            "wake_count": self.state.wake_count,
            "commands_processed": self.state.commands_processed,
        }
