import json
import os
from typing import Optional, Dict

class SelectorMemory:
    """Caches successful selectors and tracks failures."""
    
    def __init__(self, cache_path: str = "data/ui_vision/selector_cache.json"):
        self.cache_path = cache_path
        self.memory = self._load()

    def _load(self) -> Dict[str, str]:
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r") as f:
                return json.load(f)
        return {}

    def save_success(self, query: str, resolved_selector: str):
        self.memory[query] = resolved_selector
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump(self.memory, f)

    def get_cached(self, query: str) -> Optional[str]:
        return self.memory.get(query)

    def log_failure(self, query: str, selector: str, reason: str):
        log_path = "data/logs/selector_failures.log"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"Query: {query} | Selector: {selector} | Reason: {reason}\n")
