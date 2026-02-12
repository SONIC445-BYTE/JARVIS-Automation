
# AgentCore/knowledge/query_expander.py

from typing import List

def expand_query(query: str) -> List[str]:
    """
    Expand query into search variants.
    """
    variants = [query]
    
    lower_q = query.lower()
    if "who is" in lower_q:
        variants.append(lower_q.replace("who is", "current"))
    if "president" in lower_q:
        variants.append(lower_q + " latest news")
        
    return variants
