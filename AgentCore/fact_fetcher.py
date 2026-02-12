import requests
import urllib.parse
from bs4 import BeautifulSoup
try:
    import wikipedia
except ImportError:
    wikipedia = None

def fetch_fact(query: str) -> dict:
    """
    Fetch live fact from trusted sources (Wikipedia).
    Returns dict with 'content', 'source', 'url'.
    """
    # Try Wikipedia Library first (Cleanest)
    if wikipedia:
        try:
            # Search for best match
            results = wikipedia.search(query, results=1)
            if results:
                page = wikipedia.page(results[0], auto_suggest=False)
                return {
                    "content": page.summary[:1000], # Limit length
                    "source": "Wikipedia",
                    "url": page.url,
                    "topic": results[0]
                }
        except Exception as e:
            print(f"[FactFetcher] Wiki lib error: {e}")

    # Fallback/Default: HTML Scrape (as requested)
    try:
        # Construct Wikipedia URL
        topic = query.replace("who is ", "").replace("what is ", "").strip()
        # Capitalize for better URL match
        topic = topic.title().replace(" ", "_")
        
        url = f"https://en.wikipedia.org/wiki/{topic}"
        
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Extract first few paragraphs
            paragraphs = soup.find_all("p")
            content = ""
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 50:
                    content += text + "\n"
                    if len(content) > 500: break
            
            if content:
                return {
                    "content": content,
                    "source": "Wikipedia (Scraped)",
                    "url": url,
                    "topic": topic.replace("_", " ")
                }
                
    except Exception as e:
        print(f"[FactFetcher] Scrape error: {e}")
        
    return None
