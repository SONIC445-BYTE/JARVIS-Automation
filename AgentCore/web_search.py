from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

class WebSearch:
    def __init__(self):
        self.options = Options()
        self.options.add_argument("--headless=new")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--log-level=3")
        
        # Use existing driver manager
        self.service = Service(ChromeDriverManager().install())
    
    def search(self, query: str, num_results: int = 3) -> str:
        """
        Perform a web search and return a summary string.
        """
        driver = None
        try:
            driver = webdriver.Chrome(service=self.service, options=self.options)
            
            # Use DuckDuckGo for easier scraping (less anti-bot than Google)
            url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&ia=web"
            driver.get(url)
            
            # Wait for results
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
            )
            
            results = []
            articles = driver.find_elements(By.CSS_SELECTOR, "article")
            
            for i, article in enumerate(articles[:num_results]):
                try:
                    title = article.find_element(By.CSS_SELECTOR, "h2").text
                    snippet = article.find_element(By.CSS_SELECTOR, "[data-result='snippet']").text
                    results.append(f"Source: {title}\nSnippet: {snippet}\n")
                except:
                    continue
            
            if not results:
                return "No search results found."
                
            return "\n".join(results)
            
        except Exception as e:
            print(f"[WebSearch] Error: {e}")
            return f"Search failed: {e}"
            
        finally:
            if driver:
                driver.quit()

if __name__ == "__main__":
    ws = WebSearch()
    print(ws.search("Who is the president of USA 2025"))
