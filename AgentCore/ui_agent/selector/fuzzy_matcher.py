import difflib

class FuzzyMatcher:
    """Provides fuzzy string matching for UI elements."""
    
    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        
    def match(self, query: str, target: str) -> bool:
        """Return True if query fuzzily matches target."""
        if not query or not target:
            return False
            
        query = query.lower()
        target = target.lower()
        
        # 1. Simple substring
        if query in target:
            return True
            
        # 2. Sequence matcher ratio
        ratio = difflib.SequenceMatcher(None, query, target).ratio()
        return ratio >= self.threshold

    def find_best(self, query: str, targets: list[str]) -> tuple[str, float]:
        """Find the best match from a list of targets."""
        best_match = None
        highest_ratio = 0.0
        
        for target in targets:
            ratio = difflib.SequenceMatcher(None, query.lower(), target.lower()).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = target
                
        return best_match, highest_ratio
