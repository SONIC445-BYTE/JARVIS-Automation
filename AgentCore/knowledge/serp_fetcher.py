
# AgentCore/knowledge/serp_fetcher.py

import time
from typing import List, Dict
import urllib.parse
from contextlib import contextmanager

from .config import USER_AGENT, REQUEST_TIMEOUT

import atexit

_driver = None

def get_driver_instance():
    """
    Get or create a global persistent driver.

    selenium/webdriver_manager are imported here, not at module level --
    this is the last-resort tier of the S0-E3 provider chain and must
    not pull in a Chrome-launching dependency just because this module
    (or discovery_manager/provider_chain, which import it transitively)
    was imported. Same lazy-import discipline already applied to
    NetHyTechSTT and browser_automation.py after the 59-minute test-hang
    incident that eager Selenium/webdriver_manager imports caused there.
    """
    global _driver
    if _driver is None:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        options = Options()
        options.add_argument(f"user-agent={USER_AGENT}")
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        
        service = Service(ChromeDriverManager().install())
        _driver = webdriver.Chrome(service=service, options=options)
        _driver.set_page_load_timeout(REQUEST_TIMEOUT)
        
        # Register cleanup
        atexit.register(cleanup_driver)
        
    return _driver

def cleanup_driver():
    global _driver
    if _driver:
        try:
            _driver.quit()
        except:
            pass
        _driver = None

def fetch_serp(query: str, max_results: int = 10) -> List[Dict]:
    """Fetch SERP from DuckDuckGo using Persistent Selenium."""
    from selenium.webdriver.common.by import By

    url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"

    results = []
    try:
        driver = get_driver_instance()
        driver.get(url)
        time.sleep(1.5) # Reduced wait time since driver is warm

        # Selectors for DDG
        # result wrapper: article[data-testid="result"]
        articles = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result']")
        
        if not articles:
            # Fallback to old selectors
            articles = driver.find_elements(By.CSS_SELECTOR, ".result")
        
        for article in articles[:max_results]:
            try:
                title_elem = article.find_element(By.CSS_SELECTOR, "h2 a")
                snippet_elem = article.find_element(By.CSS_SELECTOR, "[data-result='snippet']")
                
                title = title_elem.text
                link = title_elem.get_attribute('href')
                snippet = snippet_elem.text
                
                if link and title:
                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": snippet,
                        "source": "duckduckgo"
                    })
            except Exception:
                continue
                    
    except Exception as e:
        print(f"[SERP] Selenium Error: {e}")
        
    return results
