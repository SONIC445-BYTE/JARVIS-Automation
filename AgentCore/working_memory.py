"""
Working Memory - Ephemeral Context Store
==========================================
Stores task context during execution.

Sprint 3: Task Thinking
"""

import time
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from threading import Lock


@dataclass
class MemoryEntry:
    """Single memory entry."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    task_id: Optional[str] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class WorkingMemory:
    """
    Ephemeral store for task context.
    
    Features:
    - Key-value storage
    - TTL expiration
    - Task-scoped memory
    - Checkpoint/restore
    """
    
    DEFAULT_TTL = 300  # 5 minutes
    MAX_ENTRIES = 1000
    
    def __init__(self, checkpoint_dir: Optional[Path] = None):
        self._memory: Dict[str, MemoryEntry] = {}
        self._lock = Lock()
        
        if checkpoint_dir is None:
            checkpoint_dir = Path(__file__).parent.parent / "checkpoints" / "memory"
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None, 
           task_id: Optional[str] = None):
        """
        Store a value in working memory.
        
        Args:
            key: Storage key
            value: Value to store
            ttl: Time to live in seconds (None = default)
            task_id: Associated task ID
        """
        with self._lock:
            if ttl is None:
                ttl = self.DEFAULT_TTL
            
            expires_at = time.time() + ttl if ttl > 0 else None
            
            self._memory[key] = MemoryEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                task_id=task_id
            )
            
            # Cleanup if too many entries
            if len(self._memory) > self.MAX_ENTRIES:
                self._cleanup_expired()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from memory.
        
        Args:
            key: Storage key
            default: Default if not found or expired
            
        Returns:
            Stored value or default
        """
        with self._lock:
            entry = self._memory.get(key)
            if entry is None:
                return default
            
            if entry.is_expired():
                del self._memory[key]
                return default
            
            return entry.value
    
    def delete(self, key: str):
        """Delete a key from memory."""
        with self._lock:
            self._memory.pop(key, None)
    
    def clear_task(self, task_id: str):
        """Clear all memory for a task."""
        with self._lock:
            keys_to_delete = [
                k for k, v in self._memory.items()
                if v.task_id == task_id
            ]
            for key in keys_to_delete:
                del self._memory[key]
    
    def clear_all(self):
        """Clear all memory."""
        with self._lock:
            self._memory.clear()
    
    def _cleanup_expired(self):
        """Remove expired entries (called with lock held)."""
        keys_to_delete = [
            k for k, v in self._memory.items()
            if v.is_expired()
        ]
        for key in keys_to_delete:
            del self._memory[key]
    
    # Context helpers
    
    def set_context(self, task_id: str, context: Dict):
        """Set context for a task."""
        self.set(f"context:{task_id}", context, task_id=task_id)
    
    def get_context(self, task_id: str) -> Dict:
        """Get context for a task."""
        return self.get(f"context:{task_id}", {})
    
    def update_context(self, task_id: str, updates: Dict):
        """Update context for a task."""
        ctx = self.get_context(task_id)
        ctx.update(updates)
        self.set_context(task_id, ctx)
    
    # Slot helpers (for clarification)
    
    def set_slot(self, task_id: str, slot_name: str, value: Any):
        """Set a slot value."""
        self.set(f"slot:{task_id}:{slot_name}", value, task_id=task_id)
    
    def get_slot(self, task_id: str, slot_name: str, default: Any = None) -> Any:
        """Get a slot value."""
        return self.get(f"slot:{task_id}:{slot_name}", default)
    
    # Checkpoint
    
    def checkpoint(self, name: str = "latest"):
        """Save current memory to disk."""
        checkpoint_file = self.checkpoint_dir / f"{name}.json"
        
        with self._lock:
            data = {
                k: {
                    "value": v.value,
                    "created_at": v.created_at,
                    "expires_at": v.expires_at,
                    "task_id": v.task_id
                }
                for k, v in self._memory.items()
                if not v.is_expired()
            }
        
        try:
            with open(checkpoint_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[WorkingMemory] Checkpoint error: {e}")
    
    def restore(self, name: str = "latest") -> bool:
        """Restore memory from disk."""
        checkpoint_file = self.checkpoint_dir / f"{name}.json"
        
        if not checkpoint_file.exists():
            return False
        
        try:
            with open(checkpoint_file, "r") as f:
                data = json.load(f)
            
            with self._lock:
                self._memory.clear()
                
                for key, entry_data in data.items():
                    self._memory[key] = MemoryEntry(
                        key=key,
                        **entry_data
                    )
            
            return True
            
        except Exception as e:
            print(f"[WorkingMemory] Restore error: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get memory statistics."""
        with self._lock:
            total = len(self._memory)
            expired = sum(1 for v in self._memory.values() if v.is_expired())
            by_task = {}
            
            for entry in self._memory.values():
                if entry.task_id:
                    by_task[entry.task_id] = by_task.get(entry.task_id, 0) + 1
        
        return {
            "total_entries": total,
            "expired_pending": expired,
            "by_task": by_task
        }


def test_working_memory():
    """Test working memory."""
    print("Working Memory Test")
    print("=" * 50)
    
    mem = WorkingMemory()
    
    # Basic set/get
    mem.set("test_key", "test_value")
    print(f"get('test_key') = {mem.get('test_key')}")
    
    # Task context
    mem.set_context("task_1", {"user": "john", "app": "whatsapp"})
    print(f"Context for task_1: {mem.get_context('task_1')}")
    
    # Slots
    mem.set_slot("task_1", "recipient", "Jane")
    print(f"Slot 'recipient' for task_1: {mem.get_slot('task_1', 'recipient')}")
    
    # Stats
    print(f"Stats: {mem.get_stats()}")
    
    # Checkpoint
    mem.checkpoint()
    print("Checkpointed!")


if __name__ == "__main__":
    test_working_memory()
