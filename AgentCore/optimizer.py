"""
Optimizer - Shortcut Suggestions and Task Acceleration
========================================================
Suggests shortcuts based on learned patterns.

Sprint 4: Learning & Personalization
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .pattern_engine import PatternEngine
from .memory_store import MemoryStore


@dataclass
class Shortcut:
    """Suggested shortcut/macro."""
    shortcut_id: str
    name: str
    description: str
    steps: List[str]
    trigger_phrases: List[str]
    time_saved_ms: float = 0
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)


class Optimizer:
    """
    Suggests optimizations and shortcuts.
    
    Sources:
    - Repeated action sequences
    - Common clarification resolutions
    - Frequently combined tasks
    """
    
    MIN_SEQUENCE_COUNT = 3  # Occurrences before suggesting shortcut
    
    def __init__(self, pattern_engine: PatternEngine = None,
                memory_store: MemoryStore = None):
        self.patterns = pattern_engine or PatternEngine()
        self.memory = memory_store or MemoryStore()
        
        self._action_history: List[str] = []
        self._sequence_counts: Dict[tuple, int] = {}
        self._shortcuts: Dict[str, Shortcut] = {}
        
        self._load_shortcuts()
    
    def _load_shortcuts(self):
        """Load saved shortcuts from memory."""
        shortcuts = self.memory.get_by_category("shortcut")
        for key, data in shortcuts.items():
            if isinstance(data, dict):
                self._shortcuts[key] = Shortcut(**data)
    
    def _save_shortcuts(self):
        """Save shortcuts to memory."""
        for shortcut_id, shortcut in self._shortcuts.items():
            self.memory.set(
                f"shortcut:{shortcut_id}",
                {
                    "shortcut_id": shortcut.shortcut_id,
                    "name": shortcut.name,
                    "description": shortcut.description,
                    "steps": shortcut.steps,
                    "trigger_phrases": shortcut.trigger_phrases,
                    "time_saved_ms": shortcut.time_saved_ms,
                    "usage_count": shortcut.usage_count,
                    "created_at": shortcut.created_at
                },
                category="shortcut"
            )
    
    def record_action(self, action: str, duration_ms: float = 0):
        """
        Record an action for sequence detection.
        
        Args:
            action: Action that was performed
            duration_ms: How long it took
        """
        self._action_history.append(action)
        
        # Keep last 100 actions
        if len(self._action_history) > 100:
            self._action_history = self._action_history[-100:]
        
        # Update sequence counts
        self._update_sequences()
    
    def _update_sequences(self):
        """Update sequence occurrence counts."""
        # Look for 2-3 action sequences
        for length in [2, 3]:
            if len(self._action_history) >= length:
                seq = tuple(self._action_history[-length:])
                self._sequence_counts[seq] = self._sequence_counts.get(seq, 0) + 1
    
    def get_suggestions(self) -> List[Shortcut]:
        """
        Get suggested shortcuts based on patterns.
        
        Returns:
            List of suggested shortcuts
        """
        suggestions = []
        
        for seq, count in self._sequence_counts.items():
            if count >= self.MIN_SEQUENCE_COUNT:
                # Don't suggest if already a shortcut
                seq_key = "_".join(seq)
                if seq_key not in self._shortcuts:
                    shortcut = self._create_suggestion(seq, count)
                    if shortcut:
                        suggestions.append(shortcut)
        
        # Sort by potential time savings
        suggestions.sort(key=lambda s: s.time_saved_ms, reverse=True)
        return suggestions[:5]  # Top 5
    
    def _create_suggestion(self, sequence: tuple, count: int) -> Optional[Shortcut]:
        """Create a shortcut suggestion from a sequence."""
        if len(sequence) < 2:
            return None
        
        # Generate name from actions
        first_action = sequence[0].split()[0] if sequence[0] else "do"
        last_action = sequence[-1].split()[0] if sequence[-1] else "task"
        name = f"{first_action.title()} and {last_action.title()}"
        
        # Estimate time saved
        avg_action_time = 500  # ms
        time_saved = avg_action_time * (len(sequence) - 1) * count
        
        return Shortcut(
            shortcut_id="_".join(sequence),
            name=name,
            description=f"Combines: {' → '.join(sequence)}",
            steps=list(sequence),
            trigger_phrases=[name.lower(), " and ".join(sequence)],
            time_saved_ms=time_saved
        )
    
    def create_shortcut(self, name: str, steps: List[str], 
                       triggers: List[str] = None) -> Shortcut:
        """
        Create a custom shortcut.
        
        Args:
            name: Shortcut name
            steps: Actions to perform
            triggers: Phrases that trigger this shortcut
            
        Returns:
            Created Shortcut
        """
        shortcut_id = f"custom_{len(self._shortcuts) + 1}"
        
        shortcut = Shortcut(
            shortcut_id=shortcut_id,
            name=name,
            description=f"Custom shortcut: {' → '.join(steps)}",
            steps=steps,
            trigger_phrases=triggers or [name.lower()]
        )
        
        self._shortcuts[shortcut_id] = shortcut
        self._save_shortcuts()
        
        return shortcut
    
    def find_shortcut(self, intent: str) -> Optional[Shortcut]:
        """
        Find a matching shortcut for an intent.
        
        Args:
            intent: User intent text
            
        Returns:
            Matching Shortcut or None
        """
        intent_lower = intent.lower()
        
        for shortcut in self._shortcuts.values():
            for trigger in shortcut.trigger_phrases:
                if trigger in intent_lower:
                    shortcut.usage_count += 1
                    return shortcut
        
        return None
    
    def use_shortcut(self, shortcut_id: str) -> Optional[List[str]]:
        """
        Execute a shortcut (returns steps).
        
        Args:
            shortcut_id: ID of shortcut to use
            
        Returns:
            List of action steps, or None
        """
        shortcut = self._shortcuts.get(shortcut_id)
        if shortcut:
            shortcut.usage_count += 1
            return shortcut.steps
        return None
    
    def delete_shortcut(self, shortcut_id: str) -> bool:
        """Delete a shortcut."""
        if shortcut_id in self._shortcuts:
            del self._shortcuts[shortcut_id]
            self.memory.delete(f"shortcut:{shortcut_id}")
            return True
        return False
    
    def get_all_shortcuts(self) -> List[Shortcut]:
        """Get all saved shortcuts."""
        return list(self._shortcuts.values())
    
    def get_stats(self) -> Dict:
        """Get optimizer statistics."""
        return {
            "action_history_size": len(self._action_history),
            "unique_sequences": len(self._sequence_counts),
            "saved_shortcuts": len(self._shortcuts),
            "top_sequences": sorted(
                [(seq, count) for seq, count in self._sequence_counts.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }


def test_optimizer():
    """Test optimizer."""
    print("Optimizer Test")
    print("=" * 50)
    
    optimizer = Optimizer()
    
    # Simulate repeated sequence
    for _ in range(4):
        optimizer.record_action("open chrome")
        optimizer.record_action("go to gmail.com")
        optimizer.record_action("click compose")
    
    # Get suggestions
    suggestions = optimizer.get_suggestions()
    print(f"Suggestions: {len(suggestions)}")
    for s in suggestions:
        print(f"  - {s.name}: {s.steps}")
    
    # Create custom shortcut
    shortcut = optimizer.create_shortcut(
        "Morning Email",
        ["open chrome", "go to gmail.com", "click compose"],
        triggers=["check email", "morning email"]
    )
    print(f"\nCreated shortcut: {shortcut.name}")
    
    # Find shortcut
    found = optimizer.find_shortcut("I want to check email")
    print(f"Found: {found.name if found else 'None'}")
    
    # Stats
    print(f"\nStats: {optimizer.get_stats()}")


if __name__ == "__main__":
    test_optimizer()
