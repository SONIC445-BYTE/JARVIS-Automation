from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse, urljoin
import time

class BrowserAdapter:
    """
    Enhanced Browser Adapter with semantic validation and URL handling.
    Supports both direct URL navigation and domain-based navigation.
    """
    
    def __init__(self, driver_type: str = "selenium"):
        self.driver_type = driver_type
        self.driver = None
        self.current_url = None
        
    def _ensure_http(self, url: str) -> str:
        """Ensure URL has proper scheme."""
        if not url.startswith(('http://', 'https://')):
            return f'https://{url}'
        return url
    
    def _resolve_domain(self, domain: str) -> str:
        """Resolve common domain names to their full URLs."""
        domain_map = {
            'google': 'https://www.google.com',
            'youtube': 'https://www.youtube.com',
            'gmail': 'https://mail.google.com'
        }
        return domain_map.get(domain.lower(), f'https://www.{domain}.com')
    
    def open_url(self, url: str) -> bool:
        """
        Open a URL or resolve a domain name.
        Returns True if navigation was successful.
        """
        try:
            # Handle domain names without protocol
            if not url.startswith(('http://', 'https://')):
                if '.' not in url:  # Likely a domain name without TLD
                    url = self._resolve_domain(url)
                else:
                    url = self._ensure_http(url)
            
            print(f"[Browser] Navigating to {url}")
            # In a real implementation, this would use Selenium/Playwright
            # self.driver.get(url)
            self.current_url = url
            return self.is_page_loaded()
        except Exception as e:
            print(f"[Browser] Failed to navigate: {str(e)}")
            return False
    
    def is_page_loaded(self, expected_content: str = None, timeout: int = 10) -> bool:
        """
        Verify if page is loaded and contains expected content.
        
        Args:
            expected_content: Optional string that should be present in page
            timeout: Maximum time to wait for page load (seconds)
            
        Returns:
            bool: True if page is loaded and contains expected content
        """
        if not self.driver:
            # In a real implementation, check driver's page state
            # For now, simulate successful load after a short delay
            time.sleep(1)
            return True
            
        try:
            # Check document.readyState
            ready = self.driver.execute_script("return document.readyState == 'complete'")
            if not ready:
                return False
                
            # Check for expected content if provided
            if expected_content:
                page_source = self.driver.page_source.lower()
                return expected_content.lower() in page_source
                
            return True
        except Exception as e:
            print(f"[Browser] Page load check failed: {str(e)}")
            return False
    
    def get_elements(self, selector: str) -> List[Dict]:
        """
        Find elements matching the given selector.
        
        Returns:
            List of element dictionaries with properties
        """
        if not self.driver:
            return []
            
        try:
            # In a real implementation, this would use Selenium/Playwright
            # elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            # return [self._element_to_dict(el) for el in elements]
            return []
        except Exception as e:
            print(f"[Browser] Failed to find elements: {str(e)}")
            return []
    
    def perform_action(self, selector: str, action: str, value: Any = None) -> Tuple[bool, str]:
        """
        Perform an action on a web element.
        
        Args:
            selector: CSS selector to find the element
            action: Action to perform (click, type, etc.)
            value: Optional value for actions like type
            
        Returns:
            Tuple of (success, message)
        """
        try:
            elements = self.get_elements(selector)
            if not elements:
                return False, f"No elements found matching: {selector}"
                
            element = elements[0]  # Use first matching element
            
            if action == "click":
                # element.click()
                return True, f"Clicked {selector}"
                
            elif action == "type":
                if not value:
                    return False, "No value provided for type action"
                # element.clear()
                # element.send_keys(value)
                return True, f"Typed '{value}' into {selector}"
                
            elif action == "enter":
                # element.send_keys(Keys.RETURN)
                return True, f"Pressed ENTER in {selector}"
                
            return False, f"Unsupported action: {action}"
            
        except Exception as e:
            return False, f"Action failed: {str(e)}"
