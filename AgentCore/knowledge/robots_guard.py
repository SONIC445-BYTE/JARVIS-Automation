
# AgentCore/knowledge/robots_guard.py

import urllib.robotparser
from urllib.parse import urlparse
from .config import USER_AGENT

_robots_cache = {}

def allowed(url: str, user_agent: str = USER_AGENT) -> bool:
    """Check if URL is allowed by robots.txt."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base_url}/robots.txt"
    
    if base_url not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
             # If robots.txt fetch fails, assume allowed (per standard) or disallowed (per strict)
             # Standard convention is allowed if robots.txt missing/error
            pass
        _robots_cache[base_url] = rp
    
    return _robots_cache[base_url].can_fetch(user_agent, url)

def get_crawl_delay(url: str, user_agent: str = USER_AGENT) -> float:
    """Get crawl delay from robots.txt."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    if base_url in _robots_cache:
        return _robots_cache[base_url].crawl_delay(user_agent) or 0.0
    return 0.0
