"""
Feedback Engine - Learn from Success/Failure
==============================================
Captures explicit and implicit feedback to improve accuracy.

Sprint 4: Learning & Personalization
"""

import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum

from .pattern_engine import PatternEngine
from .memory_store import MemoryStore


class FeedbackType(Enum):
    """Types of feedback signals."""
    EXPLICIT_POSITIVE = "explicit_positive"   # User said "yes", "correct"
    EXPLICIT_NEGATIVE = "explicit_negative"   # User said "no", "wrong"
    IMPLICIT_SUCCESS = "implicit_success"     # Action completed successfully
    IMPLICIT_FAILURE = "implicit_failure"     # Action failed/was cancelled
    CORRECTION = "correction"                  # User provided correction


@dataclass
class FeedbackRecord:
    """Single feedback record."""
    action_id: str
    intent: str
    feedback_type: FeedbackType
    timestamp: float = field(default_factory=time.time)
    details: Dict = field(default_factory=dict)
    correction: Optional[str] = None


class FeedbackEngine:
    """
    Captures and processes feedback signals.
    
    Feedback sources:
    - Explicit: user says "wrong", "correct", etc.
    - Implicit: action success/failure
    - Corrections: user provides the right answer
    """
    
    def __init__(self, pattern_engine: PatternEngine = None, 
                memory_store: MemoryStore = None):
        self.patterns = pattern_engine or PatternEngine()
        self.memory = memory_store or MemoryStore()
        
        self._pending_feedback: Dict[str, FeedbackRecord] = {}
        self._feedback_history: List[FeedbackRecord] = []
        self._max_history = 1000
    
    def record_action(self, action_id: str, intent: str, 
                     metadata: Dict = None) -> str:
        """
        Record an action to await feedback.
        
        Args:
            action_id: Unique action identifier
            intent: The intent that was executed
            metadata: Additional action metadata
            
        Returns:
            action_id for reference
        """
        self._pending_feedback[action_id] = FeedbackRecord(
            action_id=action_id,
            intent=intent,
            feedback_type=None,  # Will be set when feedback received
            details=metadata or {}
        )
        return action_id
    
    def record_success(self, action_id: str):
        """
        Record implicit success for an action.
        
        Args:
            action_id: Action that succeeded
        """
        record = self._pending_feedback.pop(action_id, None)
        if record:
            record.feedback_type = FeedbackType.IMPLICIT_SUCCESS
            self._process_feedback(record)
    
    def record_failure(self, action_id: str, error: str = None):
        """
        Record implicit failure for an action.
        
        Args:
            action_id: Action that failed
            error: Optional error message
        """
        record = self._pending_feedback.pop(action_id, None)
        if record:
            record.feedback_type = FeedbackType.IMPLICIT_FAILURE
            record.details["error"] = error
            self._process_feedback(record)
    
    def record_explicit_feedback(self, action_id: str, positive: bool):
        """
        Record explicit user feedback.
        
        Args:
            action_id: Action being rated
            positive: True for positive, False for negative
        """
        record = self._pending_feedback.pop(action_id, None)
        if record:
            record.feedback_type = (
                FeedbackType.EXPLICIT_POSITIVE if positive 
                else FeedbackType.EXPLICIT_NEGATIVE
            )
            self._process_feedback(record)
    
    def record_correction(self, action_id: str, correct_value: str):
        """
        Record user's correction.
        
        Args:
            action_id: Action that was wrong
            correct_value: What it should have been
        """
        record = self._pending_feedback.pop(action_id, None)
        if record:
            record.feedback_type = FeedbackType.CORRECTION
            record.correction = correct_value
            self._process_feedback(record)
    
    def _process_feedback(self, record: FeedbackRecord):
        """Process feedback and update pattern engine."""
        # Add to history
        self._feedback_history.append(record)
        if len(self._feedback_history) > self._max_history:
            self._feedback_history = self._feedback_history[-self._max_history:]
        
        # Update pattern engine
        success = record.feedback_type in [
            FeedbackType.EXPLICIT_POSITIVE,
            FeedbackType.IMPLICIT_SUCCESS
        ]
        
        # Extract pattern key from intent
        pattern_key = self._intent_to_pattern(record.intent)
        self.patterns.record_usage(pattern_key, success=success)
        
        # Store corrections in memory
        if record.feedback_type == FeedbackType.CORRECTION:
            self.memory.set(
                f"correction:{pattern_key}",
                {
                    "original": record.intent,
                    "correction": record.correction,
                    "timestamp": record.timestamp
                },
                category="correction"
            )
        
        # Learn from failures
        if record.feedback_type == FeedbackType.IMPLICIT_FAILURE:
            self._learn_from_failure(record)
    
    def _intent_to_pattern(self, intent: str) -> str:
        """Convert intent to pattern key."""
        # Simple: use first two words
        words = intent.lower().split()[:2]
        return "intent:" + "_".join(words)
    
    def _learn_from_failure(self, record: FeedbackRecord):
        """Learn from a failure to prevent repeats."""
        pattern_key = self._intent_to_pattern(record.intent)
        
        # Track failure reason
        failure_key = f"failure:{pattern_key}"
        failures = self.memory.get(failure_key, [])
        failures.append({
            "error": record.details.get("error"),
            "timestamp": record.timestamp
        })
        
        # Keep last 10 failures
        self.memory.set(failure_key, failures[-10:], category="failure")
    
    def get_correction(self, intent: str) -> Optional[str]:
        """
        Get stored correction for an intent.
        
        Args:
            intent: Intent to check
            
        Returns:
            Correction string if exists, None otherwise
        """
        pattern_key = self._intent_to_pattern(intent)
        data = self.memory.get(f"correction:{pattern_key}")
        return data.get("correction") if data else None
    
    def should_avoid(self, intent: str, threshold: int = 3) -> bool:
        """
        Check if intent has failed too many times.
        
        Args:
            intent: Intent to check
            threshold: Failure count to warn
            
        Returns:
            True if should avoid/warn
        """
        pattern_key = self._intent_to_pattern(intent)
        failures = self.memory.get(f"failure:{pattern_key}", [])
        return len(failures) >= threshold
    
    def get_success_rate(self, intent: str) -> float:
        """Get success rate for an intent type."""
        pattern_key = self._intent_to_pattern(intent)
        return self.patterns.get_score(pattern_key)
    
    def get_stats(self) -> Dict:
        """Get feedback statistics."""
        by_type = {}
        for record in self._feedback_history:
            if record.feedback_type:
                ft = record.feedback_type.value
                by_type[ft] = by_type.get(ft, 0) + 1
        
        return {
            "total_feedback": len(self._feedback_history),
            "pending_actions": len(self._pending_feedback),
            "by_type": by_type
        }


def test_feedback_engine():
    """Test feedback engine."""
    print("Feedback Engine Test")
    print("=" * 50)
    
    engine = FeedbackEngine()
    
    # Record an action
    action_id = engine.record_action("action_1", "open notepad")
    print(f"Recorded action: {action_id}")
    
    # Record success
    engine.record_success(action_id)
    print("Recorded success")
    
    # Record another action with failure
    action2 = engine.record_action("action_2", "send email to boss")
    engine.record_failure(action2, "recipient not found")
    print("Recorded failure")
    
    # Record correction
    action3 = engine.record_action("action_3", "open chrome")
    engine.record_correction(action3, "open firefox")
    print("Recorded correction")
    
    # Check stats
    print(f"Stats: {engine.get_stats()}")
    
    # Get correction
    correction = engine.get_correction("open chrome")
    print(f"Correction for 'open chrome': {correction}")


if __name__ == "__main__":
    test_feedback_engine()
