"""
Conversation Loop - Continuous Spoken Dialogue
=================================================
State machine for multi-turn conversation.

Sprint 6: Conversational Intelligence
"""

import time
from typing import Optional, Callable, Dict
from enum import Enum
from dataclasses import dataclass
from threading import Thread, Event


class ConversationState(Enum):
    """Conversation states."""
    SLEEP = "sleep"         # Waiting for wake word
    WAKE = "wake"           # Just woke up
    LISTEN = "listen"       # Listening for user input
    THINK = "think"         # Processing input
    SPEAK = "speak"         # Speaking response
    EXECUTE = "execute"     # Executing action
    CONFIRM = "confirm"     # Waiting for confirmation


@dataclass
class LoopConfig:
    """Conversation loop configuration."""
    silence_timeout: float = 15.0    # Seconds before sleep
    listen_timeout: float = 10.0     # Max listen time
    think_timeout: float = 30.0      # Max LLM time
    max_turns: int = 20              # Max turns before forced sleep
    auto_sleep_after_action: bool = False


class ConversationLoop:
    """
    Manages continuous spoken dialogue.
    
    State Flow:
    SLEEP → WAKE → LISTEN → THINK → SPEAK → LISTEN (loop)
                                  ↓
                             EXECUTE → SPEAK → LISTEN
    
    Exit conditions:
    - 15s silence → SLEEP
    - User says goodbye → SLEEP
    - Max turns reached → SLEEP
    """
    
    GOODBYE_PHRASES = ["goodbye", "bye", "go to sleep", "stop listening", "that's all"]
    
    def __init__(self, config: LoopConfig = None):
        self.config = config or LoopConfig()
        self.state = ConversationState.SLEEP
        
        # Callbacks
        self.on_wake: Optional[Callable] = None
        self.on_listen: Optional[Callable[[], Optional[str]]] = None
        self.on_think: Optional[Callable[[str], str]] = None
        self.on_speak: Optional[Callable[[str], None]] = None
        self.on_execute: Optional[Callable[[str], tuple]] = None
        self.on_sleep: Optional[Callable] = None
        
        self._running = Event()
        self._loop_thread: Optional[Thread] = None
        self._current_turn = 0
        self._last_activity = time.time()
        
        print("[ConversationLoop] Initialized")
    
    def start(self):
        """Start the conversation loop."""
        if self._running.is_set():
            return
        
        self._running.set()
        self._loop_thread = Thread(target=self._loop, daemon=True)
        self._loop_thread.start()
        print("[ConversationLoop] Started")
    
    def stop(self):
        """Stop the conversation loop."""
        self._running.clear()
        if self._loop_thread:
            self._loop_thread.join(timeout=5)
        print("[ConversationLoop] Stopped")
    
    def wake(self):
        """Trigger wake (called by wake detector)."""
        if self.state == ConversationState.SLEEP:
            self._set_state(ConversationState.WAKE)
            self._current_turn = 0
    
    def _set_state(self, new_state: ConversationState):
        """Transition to new state."""
        old_state = self.state
        self.state = new_state
        self._last_activity = time.time()
        print(f"[ConversationLoop] {old_state.value} → {new_state.value}")
    
    def _loop(self):
        """Main conversation loop."""
        while self._running.is_set():
            try:
                if self.state == ConversationState.SLEEP:
                    # Just wait, wake word detector handles waking
                    time.sleep(0.5)
                    
                elif self.state == ConversationState.WAKE:
                    self._handle_wake()
                    
                elif self.state == ConversationState.LISTEN:
                    self._handle_listen()
                    
                elif self.state == ConversationState.THINK:
                    # Handled in listen
                    time.sleep(0.1)
                    
                elif self.state == ConversationState.SPEAK:
                    # Handled after think
                    time.sleep(0.1)
                    
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"[ConversationLoop] Error: {e}")
                self._set_state(ConversationState.SLEEP)
    
    def _handle_wake(self):
        """Handle wake state."""
        # Call wake callback
        if self.on_wake:
            self.on_wake()
        
        # Speak greeting
        if self.on_speak:
            self.on_speak("Yes?")
        
        self._set_state(ConversationState.LISTEN)
    
    def _handle_listen(self):
        """Handle listen state."""
        # Check silence timeout
        if time.time() - self._last_activity > self.config.silence_timeout:
            self._go_to_sleep("Silence timeout")
            return
        
        # Check max turns
        if self._current_turn >= self.config.max_turns:
            self._go_to_sleep("Max turns reached")
            return
        
        # Get user input
        user_input = None
        if self.on_listen:
            user_input = self.on_listen()
        
        if not user_input:
            time.sleep(0.5)
            return
        
        self._last_activity = time.time()
        self._current_turn += 1
        
        # Check for goodbye
        if self._is_goodbye(user_input):
            if self.on_speak:
                self.on_speak("Goodbye.")
            self._go_to_sleep("User said goodbye")
            return
        
        # Process input
        self._set_state(ConversationState.THINK)
        
        # Check if action or conversation
        response = None
        is_action = self._is_action(user_input)
        
        if is_action and self.on_execute:
            # Execute action
            self._set_state(ConversationState.EXECUTE)
            success, result = self.on_execute(user_input)
            
            if success:
                response = result or "Done."
            else:
                response = result or "I couldn't complete that action."
        
        elif self.on_think:
            # LLM response
            response = self.on_think(user_input)
        
        if not response:
            response = "I didn't understand that."
        
        # Speak response
        self._set_state(ConversationState.SPEAK)
        if self.on_speak:
            self.on_speak(response)
        
        # Return to listening (or sleep after action)
        if is_action and self.config.auto_sleep_after_action:
            self._go_to_sleep("Action complete")
        else:
            self._set_state(ConversationState.LISTEN)
    
    def _is_goodbye(self, text: str) -> bool:
        """Check if text is a goodbye."""
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in self.GOODBYE_PHRASES)
    
    def _is_action(self, text: str) -> bool:
        """Check if text is an action command."""
        action_starters = [
            "open", "close", "launch", "start", "run",
            "search", "go to", "navigate", "send", "upload",
            "download", "play", "stop", "type", "click"
        ]
        text_lower = text.lower()
        return any(text_lower.startswith(s) for s in action_starters)
    
    def _go_to_sleep(self, reason: str):
        """Transition to sleep."""
        print(f"[ConversationLoop] Going to sleep: {reason}")
        
        if self.on_sleep:
            self.on_sleep()
        
        self._set_state(ConversationState.SLEEP)
    
    def get_status(self) -> Dict:
        """Get current status."""
        return {
            "state": self.state.value,
            "turn": self._current_turn,
            "seconds_since_activity": int(time.time() - self._last_activity),
            "running": self._running.is_set()
        }


def test_conversation_loop():
    """Test conversation loop."""
    print("Conversation Loop Test")
    print("=" * 50)
    
    loop = ConversationLoop()
    
    # Set up simple callbacks
    loop.on_wake = lambda: print("  [Wake callback]")
    loop.on_speak = lambda t: print(f"  [Speak] {t}")
    loop.on_sleep = lambda: print("  [Sleep callback]")
    
    print(f"Initial state: {loop.state.value}")
    
    # Simulate wake
    loop.wake()
    print(f"After wake: {loop.state.value}")
    
    # Status
    print(f"Status: {loop.get_status()}")


if __name__ == "__main__":
    test_conversation_loop()
