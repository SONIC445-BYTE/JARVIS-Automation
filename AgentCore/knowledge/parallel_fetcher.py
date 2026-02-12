
# AgentCore/knowledge/parallel_fetcher.py

import concurrent.futures
from typing import List, Dict
from .source_adapter import fetch_and_parse
from .config import CONCURRENCY

def fetch_many(urls: List[str]) -> List[Dict]:
    """Fetch multiple URLs in parallel."""
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_to_url = {executor.submit(fetch_and_parse, url): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as e:
                print(f"[ParallelFetch] Error fetching {url}: {e}")
                results.append({"url": url, "error": str(e)})
                
    return results
