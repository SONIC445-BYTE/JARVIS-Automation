
# AgentCore/knowledge/trust_scorer.py

from urllib.parse import urlparse

TRUST_DOMAINS = [".gov", ".edu", ".mil"]
KNOWN_RELIABLE = ["wikipedia.org", "reuters.com", "apnews.com", "bbc.com", "npr.org"]
BLACKLIST = ["opinion", "blog", "social"] # Simplified

def score_source(url: str, content: str = "") -> float:
    """Calculate trust score (0.0 - 1.0)."""
    score = 0.5 # Baseline
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # 1. TLD Boost
    for tld in TRUST_DOMAINS:
        if domain.endswith(tld):
            score += 0.3
            
    # 2. Known Reliable Boost
    for reliable in KNOWN_RELIABLE:
        if reliable in domain:
            score += 0.25
            
    # 3. HTTPS
    if parsed.scheme == "https":
        score += 0.1
        
    # 4. Content Heuristics (Simple)
    if len(content) > 500: # Substantial content
        score += 0.1
        
    # Penalties
    for bad in BLACKLIST:
        if bad in domain:
            score -= 0.3
            
    return max(0.0, min(1.0, score))
