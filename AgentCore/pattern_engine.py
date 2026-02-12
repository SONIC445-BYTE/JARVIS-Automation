"""
Pattern Engine - Preference Ranking & Pattern Extraction
==========================================================
Learns from usage patterns to improve suggestions.

Sprint 4: Learning & Personalization
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import math


@dataclass
class UsagePattern:
    """Tracked usage pattern."""
    pattern_key: str
    frequency: int = 0
    last_used: float = 0
    first_used: float = 0
    success_count: int = 0
    failure_count: int = 0
    context_tags: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5
    
    @property
    def recency_score(self) -> float:
        """Score based on how recently used (decays over time)."""
        if self.last_used == 0:
            return 0
        
        hours_ago = (time.time() - self.last_used) / 3600
        # Half-life of 24 hours
        return math.exp(-hours_ago / 24)


class PatternEngine:
    """
    Learns user patterns and ranks preferences.
    
    Uses:
    - Frequency (how often used)
    - Recency (how recently used)  
    - Success rate (positive outcomes)
    """
    
    # Weights for ranking score
    FREQUENCY_WEIGHT = 0.3
    RECENCY_WEIGHT = 0.4
    SUCCESS_WEIGHT = 0.3
    
    def __init__(self):
        self._patterns: Dict[str, UsagePattern] = {}
        self._context_patterns: Dict[str, Dict[str, UsagePattern]] = defaultdict(dict)
    
    def record_usage(self, pattern_key: str, success: bool = True, 
                    context: str = None):
        """
        Record a pattern usage.
        
        Args:
            pattern_key: Unique pattern identifier
            success: Whether the action was successful
            context: Optional context (time of day, app, etc.)
        """
        now = time.time()
        
        if pattern_key not in self._patterns:
            self._patterns[pattern_key] = UsagePattern(
                pattern_key=pattern_key,
                first_used=now
            )
        
        pattern = self._patterns[pattern_key]
        pattern.frequency += 1
        pattern.last_used = now
        
        if success:
            pattern.success_count += 1
        else:
            pattern.failure_count += 1
        
        # Track context-specific patterns
        if context:
            if pattern_key not in self._context_patterns[context]:
                self._context_patterns[context][pattern_key] = UsagePattern(
                    pattern_key=pattern_key,
                    first_used=now
                )
            
            ctx_pattern = self._context_patterns[context][pattern_key]
            ctx_pattern.frequency += 1
            ctx_pattern.last_used = now
            if success:
                ctx_pattern.success_count += 1
            else:
                ctx_pattern.failure_count += 1
    
    def get_score(self, pattern_key: str, context: str = None) -> float:
        """
        Get ranking score for a pattern.
        
        Args:
            pattern_key: Pattern to score
            context: Optional context for context-aware scoring
            
        Returns:
            Score between 0 and 1
        """
        pattern = self._patterns.get(pattern_key)
        if not pattern:
            return 0.0
        
        # Normalize frequency (logarithmic)
        max_freq = max(p.frequency for p in self._patterns.values()) if self._patterns else 1
        freq_score = math.log1p(pattern.frequency) / math.log1p(max_freq)
        
        # Calculate score
        score = (
            self.FREQUENCY_WEIGHT * freq_score +
            self.RECENCY_WEIGHT * pattern.recency_score +
            self.SUCCESS_WEIGHT * pattern.success_rate
        )
        
        # Boost if context matches
        if context and pattern_key in self._context_patterns.get(context, {}):
            ctx_pattern = self._context_patterns[context][pattern_key]
            if ctx_pattern.frequency > 0:
                score *= 1.2  # 20% boost for context match
        
        return min(score, 1.0)
    
    def rank_choices(self, choices: List[str], context: str = None) -> List[Tuple[str, float]]:
        """
        Rank a list of choices by preference.
        
        Args:
            choices: List of choice keys
            context: Optional context
            
        Returns:
            List of (choice, score) tuples, sorted by score descending
        """
        scored = [(c, self.get_score(c, context)) for c in choices]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def get_preferred(self, category: str, context: str = None) -> Optional[str]:
        """
        Get the most preferred pattern in a category.
        
        Args:
            category: Category prefix to filter by
            context: Optional context
            
        Returns:
            Most preferred pattern key, or None
        """
        matching = [k for k in self._patterns.keys() if k.startswith(category)]
        
        if not matching:
            return None
        
        ranked = self.rank_choices(matching, context)
        return ranked[0][0] if ranked else None
    
    def get_patterns_for_context(self, context: str) -> List[str]:
        """Get patterns commonly used in a context."""
        if context not in self._context_patterns:
            return []
        
        patterns = list(self._context_patterns[context].keys())
        return sorted(patterns, 
                     key=lambda k: self._context_patterns[context][k].frequency,
                     reverse=True)
    
    def extract_sequences(self, pattern_keys: List[str], min_support: int = 2) -> List[List[str]]:
        """
        Extract common sequences from pattern history.
        
        Args:
            pattern_keys: Ordered list of recent patterns
            min_support: Minimum occurrences to consider
            
        Returns:
            List of common sequences
        """
        # Simple 2-gram extraction
        sequences = defaultdict(int)
        
        for i in range(len(pattern_keys) - 1):
            seq = (pattern_keys[i], pattern_keys[i + 1])
            sequences[seq] += 1
        
        return [list(seq) for seq, count in sequences.items() if count >= min_support]
    
    def decay_old_patterns(self, max_age_days: int = 30):
        """
        Decay patterns that haven't been used recently.
        
        Args:
            max_age_days: Patterns older than this may be cleaned up
        """
        cutoff = time.time() - (max_age_days * 24 * 3600)
        
        to_remove = [
            k for k, p in self._patterns.items()
            if p.last_used < cutoff and p.frequency < 5
        ]
        
        for key in to_remove:
            del self._patterns[key]
    
    def get_stats(self) -> Dict:
        """Get pattern statistics."""
        return {
            "total_patterns": len(self._patterns),
            "total_contexts": len(self._context_patterns),
            "top_patterns": sorted(
                [(k, p.frequency) for k, p in self._patterns.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


def test_pattern_engine():
    """Test pattern engine."""
    print("Pattern Engine Test")
    print("=" * 50)
    
    engine = PatternEngine()
    
    # Record some usage
    engine.record_usage("app:chrome", success=True, context="morning")
    engine.record_usage("app:chrome", success=True, context="morning")
    engine.record_usage("app:outlook", success=True, context="morning")
    engine.record_usage("app:spotify", success=True, context="evening")
    engine.record_usage("app:chrome", success=True, context="evening")
    
    # Get scores
    print(f"Chrome score: {engine.get_score('app:chrome'):.2f}")
    print(f"Outlook score: {engine.get_score('app:outlook'):.2f}")
    
    # Rank choices
    choices = ["app:chrome", "app:outlook", "app:spotify"]
    ranked = engine.rank_choices(choices, context="morning")
    print(f"Morning ranking: {ranked}")
    
    # Get preferred
    preferred = engine.get_preferred("app:", context="morning")
    print(f"Preferred app in morning: {preferred}")
    
    # Stats
    print(f"Stats: {engine.get_stats()}")


if __name__ == "__main__":
    test_pattern_engine()
