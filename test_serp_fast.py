import requests
from bs4 import BeautifulSoup
import urllib.parse
from AgentCore.knowledge.config import USER_AGENT

def test_requests_serp():
    query = "current president of USA"
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": USER_AGENT}
    
    print(f"Fetching {url} with UA: {USER_AGENT[:20]}...")
    start = __import__('time').time()
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Time: {__import__('time').time() - start:.2f}s")
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.select(".result")
            print(f"Found {len(results)} results")
            for r in results[:3]:
                title = r.select_one(".result__a").get_text(strip=True)
                print(f"- {title}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_requests_serp()
