
# AgentCore/knowledge/discovery_manager.py

from typing import List, Dict
from .serp_fetcher import fetch_serp
from .query_expander import expand_query
from .config import MAX_CANDIDATES

def discover_sources(query: str) -> List[Dict]:
    """
    Discover candidate sources for a query.
    1. Expand query
    2. Fetch SERP for each
    3. Deduplicate
    """
    variants = expand_query(query)
    all_candidates = []
    seen_urls = set()
    
    for q in variants:
        # Fetch from DDG
        results = fetch_serp(q, max_results=5)
        
        for res in results:
            url = res['url']
            if url and url not in seen_urls:
                all_candidates.append(res)
                seen_urls.add(url)
                
        if len(all_candidates) >= MAX_CANDIDATES:
            break
            
    return all_candidates[:MAX_CANDIDATES]
