from os import getcwd

website = "https://allorizenproject1.netlify.app/"
Recog_File = f"{getcwd()}\\input.txt"

_driver = None


def _get_driver():
    """
    Lazily creates the Chrome/Selenium driver on first real use of
    listen(), not at module import time. This module used to
    unconditionally download chromedriver, launch a real headless Chrome,
    and navigate to an external site as side effects of merely being
    imported -- none of those three steps has a timeout, so importing
    this module (transitively, via jarvis.py -> co_brain.py) hung the
    full pytest suite dead during test collection on a real machine with
    real network/Chrome, the same "eager import drags in a heavy
    subsystem" shape as the earlier pyautogui/mss AgentCore coupling fix.

    The selenium/webdriver_manager imports themselves are also lazy, not
    just the driver construction below -- confirmed live that `import
    jarvis` still had 'selenium'/'webdriver_manager' in sys.modules with
    only the construction deferred, since those top-level `from selenium
    import ...` statements ran regardless. Moved here so a bare `import
    jarvis` pulls in neither the library nor the driver.
    """
    global _driver
    if _driver is None:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        chrome_options = Options()
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        _driver = webdriver.Chrome(service=service, options=chrome_options)
        _driver.get(website)
    return _driver


def listen():
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    driver = _get_driver()
    try:
        start_button = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, 'startButton')))
        start_button.click()
        print("Listening...")
        output_text = ""
        is_second_click = False
        while True:
            output_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'output')))
            current_text = output_element.text.strip()
            if "Start Listening" in start_button.text and is_second_click:
                if output_text:
                    is_second_click = False
            elif "Listening..." in start_button.text:
                is_second_click = True
            if current_text != output_text:
                output_text = current_text
                with open(Recog_File, "w") as file:
                    file.write(output_text.lower())
                    print("User:", output_text)
    except KeyboardInterrupt:
        print("Process interrupted by user.")
    except Exception as e:
        print("An error occurred:", e)
    finally:
        driver.quit()