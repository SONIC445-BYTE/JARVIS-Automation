
# AgentCore/knowledge/evidence_comparator.py

from typing import List, Dict
import collections

def compare_claims(sources: List[Dict]) -> Dict:
    """
    Compare facts across sources.
    Simplified version: Aggregates snippets and checks for consistency.
    """
    # In a full impl, we'd use NER/Regex to extract entities/dates.
    # Here we perform basic text analysis.
    
    valid_sources = [s for s in sources if s.get("status") == "success"]
    
    if not valid_sources:
        return {"verdict": "UNKNOWN", "confidence": 0.0, "summary": "No valid sources found."}
    
    # Check consistency? (Hard without LLM/NLP)
    # Strategy: Just bundle them for the LLM to verify.
    # The LLM is the best "evidence comparator" we have offline-ish.
    
    # We rank confidence based on trust scores
    avg_trust = 0
    if valid_sources:
        avg_trust = sum(s.get("trust_score", 0) for s in valid_sources) / len(valid_sources)
        
    verdict = "CONFIRMED" if avg_trust > 0.6 else "UNCERTAIN"
    
    return {
        "verdict": verdict,
        "confidence": avg_trust,
        "source_count": len(valid_sources),
        "sources": valid_sources
    }
