
# AgentCore/knowledge/tests/test_end_to_end.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from AgentCore.knowledge import resolve_knowledge

def test_president_query():
    query = "current president of USA"
    print(f"Testing Query: {query}")
    
    result = resolve_knowledge(query, force_refresh=True)
    
    print("\n=== Result Bundle ===")
    print(f"Verdict: {result.get('verdict')}")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Source Count: {result.get('source_count')}")
    
    print("\n=== Top Sources ===")
    for s in result.get('sources', []):
        print(f"- [{s.get('trust_score'):.2f}] {s.get('title')} ({s.get('url')})")
        
if __name__ == "__main__":
    test_president_query()
