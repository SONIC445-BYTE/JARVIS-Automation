import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

try:
    logger.info("Initializing Chrome Options...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    logger.info("Installing ChromeDriver...")
    driver_path = ChromeDriverManager().install()
    logger.info(f"ChromeDriver installed at: {driver_path}")
    service = Service(driver_path)
    
    logger.info("Starting WebDriver...")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    logger.info("Navigating to Google...")
    driver.set_page_load_timeout(30)
    driver.get("https://www.google.com")
    logger.info(f"Title: {driver.title}")
    
    driver.quit()
    logger.info("Success!")
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    sys.exit(1)
