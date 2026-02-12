
# AgentCore/knowledge/cache_store.py

import json
import time
import os
from typing import Optional, Dict

class CacheStore:
    def __init__(self, cache_file="knowledge_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load()

    def _load(self) -> Dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"[CacheStore] Save error: {str(e)}")

    def get_cached(self, topic_key: str) -> Optional[Dict]:
        """Get cached bundle if exists."""
        return self.cache.get(topic_key)

    def set_cached(self, topic_key: str, bundle: Dict, ttl_seconds: int) -> None:
        """Store bundle with expiration."""
        expiry = time.time() + ttl_seconds
        self.cache[topic_key] = {
            "bundle": bundle,
            "expiry": expiry,
            "stored_at": time.time()
        }
        self._save()

    def invalidate(self, topic_key: str) -> None:
        if topic_key in self.cache:
            del self.cache[topic_key]
            self._save()
