"""
Conversation Manager - Multi-Turn Context
==========================================
Manages conversation history with token budgeting.

Sprint 6: Conversational Intelligence
"""

import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from collections import deque


@dataclass
class Message:
    """Single conversation message."""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    token_estimate: int = 0
    
    def __post_init__(self):
        # Rough token estimate: ~4 chars per token
        self.token_estimate = len(self.content) // 4


class ConversationManager:
    """
    Manages multi-turn conversation context.
    
    Features:
    - Rolling message window
    - Token budget management
    - TTL for old messages
    - Context summarization (when needed)
    """
    
    # Limits
    MAX_TOKENS = 1500  # Leave room for response
    MAX_MESSAGES = 20
    MESSAGE_TTL = 300  # 5 minutes
    
    def __init__(self, max_tokens: int = None, max_messages: int = None):
        self.max_tokens = max_tokens or self.MAX_TOKENS
        self.max_messages = max_messages or self.MAX_MESSAGES
        
        self._messages: deque = deque(maxlen=self.max_messages)
        self._system_prompt: Optional[str] = None
        self._total_tokens = 0
    
    def set_system(self, prompt: str):
        """Set system prompt."""
        self._system_prompt = prompt
    
    def add_user(self, content: str):
        """Add user message."""
        self._add_message(Message(role="user", content=content))
    
    def add_assistant(self, content: str):
        """Add assistant message."""
        self._add_message(Message(role="assistant", content=content))
    
    def _add_message(self, message: Message):
        """Add message and manage token budget."""
        self._messages.append(message)
        self._total_tokens += message.token_estimate
        
        # Trim if over budget
        self._trim_to_budget()
        
        # Remove expired messages
        self._remove_expired()
    
    def _trim_to_budget(self):
        """Remove oldest messages to stay within token budget."""
        while self._total_tokens > self.max_tokens and len(self._messages) > 2:
            removed = self._messages.popleft()
            self._total_tokens -= removed.token_estimate
    
    def _remove_expired(self):
        """Remove messages older than TTL."""
        now = time.time()
        cutoff = now - self.MESSAGE_TTL
        
        while self._messages and self._messages[0].timestamp < cutoff:
            # Keep at least last 2 messages
            if len(self._messages) <= 2:
                break
            removed = self._messages.popleft()
            self._total_tokens -= removed.token_estimate
    
    def get_messages(self) -> List[Dict]:
        """
        Get messages for LLM API.
        
        Returns:
            List of {"role": str, "content": str}
        """
        messages = [{"role": m.role, "content": m.content} for m in self._messages]
        return messages
    
    def get_context(self) -> tuple:
        """
        Get (system_prompt, messages) for LLM.
        
        Returns:
            (system_prompt, messages)
        """
        return (self._system_prompt, self.get_messages())
    
    def get_last_user_message(self) -> Optional[str]:
        """Get most recent user message."""
        for m in reversed(self._messages):
            if m.role == "user":
                return m.content
        return None
    
    def get_last_assistant_message(self) -> Optional[str]:
        """Get most recent assistant message."""
        for m in reversed(self._messages):
            if m.role == "assistant":
                return m.content
        return None
    
    def clear(self):
        """Clear conversation history."""
        self._messages.clear()
        self._total_tokens = 0
    
    def get_summary(self) -> Dict:
        """Get conversation summary."""
        return {
            "message_count": len(self._messages),
            "token_estimate": self._total_tokens,
            "token_budget": self.max_tokens,
            "oldest_age_seconds": (
                time.time() - self._messages[0].timestamp 
                if self._messages else 0
            )
        }
    
    def to_string(self) -> str:
        """Get conversation as readable string."""
        lines = []
        for m in self._messages:
            prefix = "You:" if m.role == "user" else "JARVIS:"
            lines.append(f"{prefix} {m.content}")
        return "\n".join(lines)


class ConversationSession:
    """
    Manages a complete conversation session.
    
    Handles:
    - Session creation/termination
    - Context persistence
    - Topic tracking
    """
    
    def __init__(self, session_id: str = None):
        import uuid
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.manager = ConversationManager()
        self.created_at = time.time()
        self.last_activity = time.time()
        self.turn_count = 0
        self.topic: Optional[str] = None
    
    def add_turn(self, user_input: str, assistant_response: str):
        """Add a complete turn (user + assistant)."""
        self.manager.add_user(user_input)
        self.manager.add_assistant(assistant_response)
        self.turn_count += 1
        self.last_activity = time.time()
    
    def is_stale(self, timeout: float = 300) -> bool:
        """Check if session is stale (no activity)."""
        return time.time() - self.last_activity > timeout
    
    def get_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.created_at


def test_conversation_manager():
    """Test conversation manager."""
    print("Conversation Manager Test")
    print("=" * 50)
    
    manager = ConversationManager()
    manager.set_system("You are JARVIS.")
    
    # Simulate conversation
    manager.add_user("Hello JARVIS")
    manager.add_assistant("Hello! How can I help you?")
    manager.add_user("What's the weather like?")
    manager.add_assistant("I don't have weather data, but I can search for it.")
    
    # Get messages
    system, messages = manager.get_context()
    print(f"System: {system}")
    print(f"Messages: {len(messages)}")
    for m in messages:
        print(f"  [{m['role']}]: {m['content'][:50]}...")
    
    # Summary
    print(f"\nSummary: {manager.get_summary()}")


if __name__ == "__main__":
    test_conversation_manager()
