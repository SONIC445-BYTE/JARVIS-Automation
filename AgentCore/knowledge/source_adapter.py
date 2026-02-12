
# AgentCore/knowledge/source_adapter.py

import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from .config import USER_AGENT, REQUEST_TIMEOUT
from .robots_guard import allowed
try:
    import trafilatura
except ImportError:
    trafilatura = None

def fetch_and_parse(url: str) -> Dict:
    """Fetch URL and parse content."""
    
    # Check robots.txt
    if not allowed(url, USER_AGENT):
        return {"error": "robots_disallowed", "url": url}
        
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return {"error": f"http_{resp.status_code}", "url": url}
            
        # Extract text using basic parsing
        # Ideally use trafilatura or readability, but let's stick to standard libs first
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Remove scripts/styles
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text = soup.get_text(separator="\n", strip=True)
        
        # Basic metadata extraction
        title = soup.title.string if soup.title else ""
        
        return {
            "url": url,
            "title": title,
            "text": text[:5000], # Limit text size
            "fetched_at": resp.headers.get('Date'),
            "status": "success"
        }
        
    except Exception as e:
        return {"error": str(e), "url": url}
