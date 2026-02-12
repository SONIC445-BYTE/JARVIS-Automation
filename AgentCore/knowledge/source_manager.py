
# AgentCore/knowledge/source_manager.py

from typing import List, Dict
from .trust_scorer import score_source
from .config import MAX_TOP_SOURCES

def select_top_sources(candidates: List[Dict]) -> List[Dict]:
    """
    Select best sources based on initial heuristics (before full fetch).
    """
    scored = []
    for c in candidates:
        # Initial score based on URL only
        score = score_source(c['url'])
        c['trust_score'] = score
        scored.append(c)
        
    # Sort by score desc
    scored.sort(key=lambda x: x['trust_score'], reverse=True)
    
    return scored[:MAX_TOP_SOURCES]
