
# AgentCore/knowledge/__init__.py

from .discovery_manager import discover_sources
from .source_manager import select_top_sources
from .parallel_fetcher import fetch_many
from .evidence_comparator import compare_claims
from .network_guard import internet_available
from .cache_store import CacheStore
from .freshness_policy import needs_refresh, get_ttl
from .trust_scorer import score_source
from typing import Dict

_cache = CacheStore()

def resolve_knowledge(query: str, force_refresh: bool = False) -> Dict:
    """
    Main entry point: Resolve query to verified knowledge bundle.
    """
    topic_key = query.lower().strip()
    
    # 1. Check Cache
    cached = _cache.get_cached(topic_key)
    if cached and not force_refresh:
        if not needs_refresh(cached):
            print(f"[Knowledge] Cache Hit for '{query}'")
            return cached['bundle']
    
    # 2. Check Internet
    if not internet_available():
        print("[Knowledge] Offline & Cache Miss")
        return {"verdict": "OFFLINE", "summary": "Internet unavailable."}
        
    print(f"[Knowledge] Discovering sources for '{query}'...")
    
    # 3. Discovery
    candidates = discover_sources(query)
    if not candidates:
        return {"verdict": "UNKNOWN", "summary": "No sources found."}
        
    # 4. Selection
    top_sources = select_top_sources(candidates)
    
    # 5. Fetching
    print(f"[Knowledge] Fetching {len(top_sources)} sources...")
    fetched_sources = fetch_many([s['url'] for s in top_sources])
    
    # Merge metadata with fetched content
    final_sources = []
    for i, fs in enumerate(fetched_sources):
        # Find original candidate metadata
        meta = next((c for c in top_sources if c['url'] == fs['url']), {})
        # Re-score based on full content
        trust = score_source(fs['url'], fs.get('text', ''))
        
        combined = {**meta, **fs, "trust_score": trust}
        if combined.get("status") == "success":
            final_sources.append(combined)
            
    # 6. Evidence Comparison
    bundle = compare_claims(final_sources)
    
    # 7. Cache
    ttl = get_ttl()
    _cache.set_cached(topic_key, bundle, ttl)
    
    return bundle
