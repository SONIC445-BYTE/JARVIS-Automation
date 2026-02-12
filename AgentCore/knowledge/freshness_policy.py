
# AgentCore/knowledge/freshness_policy.py

import time
from .config import REFRESH_POLICY

def needs_refresh(cached_entry: dict, category: str = "time_sensitive") -> bool:
    """Check if cached entry needs refresh."""
    if not cached_entry:
        return True
        
    expiry = cached_entry.get("expiry", 0)
    return time.time() > expiry

def get_ttl(category: str = "time_sensitive") -> int:
    return REFRESH_POLICY.get(category, 3600)
