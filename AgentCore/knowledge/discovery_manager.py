
# AgentCore/knowledge/discovery_manager.py

from typing import Callable, Dict, List, Optional
from .provider_chain import fetch_with_fallback
from .query_expander import expand_query
from .config import MAX_CANDIDATES

def discover_sources(query: str, notify: Optional[Callable[[str], None]] = None) -> List[Dict]:
    """
    Discover candidate sources for a query.
    1. Expand query
    2. Fetch each variant via the tiered provider chain
       (SerpApi -> Serper -> browser automation, S0-E3)
    3. Deduplicate

    notify, if given, is passed through to the provider chain so a
    caller (e.g. RAGEngine) can narrate "let me check that" / provider
    fallbacks to the user instead of it happening silently.
    """
    variants = expand_query(query)
    all_candidates = []
    seen_urls = set()

    for i, q in enumerate(variants):
        # Only narrate on the first variant -- expand_query() can add
        # several phrasings of the same underlying question, and
        # narrating "let me check that" once per variant would read as
        # confused chatter, not useful narration.
        results, _provider = fetch_with_fallback(q, max_results=5, notify=notify if i == 0 else None)

        for res in results:
            url = res['url']
            if url and url not in seen_urls:
                all_candidates.append(res)
                seen_urls.add(url)

        if len(all_candidates) >= MAX_CANDIDATES:
            break

    return all_candidates[:MAX_CANDIDATES]
