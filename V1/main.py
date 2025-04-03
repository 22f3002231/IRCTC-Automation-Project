import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from captcha_solver import solve_captcha  # CAPTCHA solving logic is kept separate

# ----------------------------------
# Configuration
# ----------------------------------
MAX_ATTEMPTS = 3
TIMEOUT = 10  # seconds for main explicit waits
FEEDBACK_TIMEOUT = 3  # shorter wait for login feedback after sign in
BASE_URL = "https://www.irctc.co.in/nget/train-search"

USERNAME = "punam7350"
PASSWORD = "Theearthian@1"

FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION   = "TATANAGAR JN - TATA (TATANAGAR)"
JOURNEY_DATE = "20/04/2025"

# For the search form:
JOURNEY_CLASS = ""
JOURNEY_QUOTA = "SLEEPER"   # We'll send its first letter ("t")
# ----------------------------------

def setup_browser():
    options = Options()
    options.page_load_strategy = 'eager'
    # Uncomment to run headless if desired:
    # options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    try:
        service = Service(executable_path=r'C:\Windows\chromedriver.exe')  # Update path if needed
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(5)
        return driver
    except Exception as e:
        logging.error(f"Browser setup failed: {e}")
        return None

def optimized_wait(driver):
    return WebDriverWait(driver, TIMEOUT)

def handle_captcha(driver, wait):
    """
    Wait for the captcha image to load, verify its src attribute is valid,
    solve it using solve_captcha(), and fill in the captcha input field.
    """
    try:
        captcha_img = wait.until(EC.visibility_of_element_located(
            (By.XPATH, "//app-captcha//img[contains(@class, 'captcha-img')]")
        ))
        captcha_src = captcha_img.get_attribute("src")
        if not captcha_src or len(captcha_src) < 50:
            logging.warning("Captcha image not loaded properly.")
            return None
        base64_data = captcha_src.split(",", 1)[-1]
        captcha_text = solve_captcha(base64_data)
        if not captcha_text or len(captcha_text) < 4:
            logging.warning("Invalid CAPTCHA solution")
            return None
        captcha_input = wait.until(EC.visibility_of_element_located((By.ID, 'captcha')))
        captcha_input.clear()
        captcha_input.send_keys(captcha_text)
        return captcha_text
    except Exception as e:
        logging.error(f"Error handling captcha: {e}")
        return None

from seleniumwire import webdriver as wire_driver

# Replace setup_browser with wire_driver
def setup_browser():
    options = Options()
    options.page_load_strategy = 'eager'
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    try:
        service = Service(executable_path=r'C:\Windows\chromedriver.exe')  # Update path if needed
        driver = wire_driver.Chrome(service=service, options=options)
        driver.implicitly_wait(5)
        return driver
    except Exception as e:
        logging.error(f"Browser setup failed: {e}")
        return None

# In login_irctc, intercept webtoken response
for request in driver.requests:
    if request.url == "https://www.irctc.co.in/authprovider/webtoken":
        if request.response:
            response_data = request.response.body.decode('utf-8')
            access_token = json.loads(response_data).get('access_token')
            if access_token:
                logging.info(f"Captured access_token from network: {access_token}")
                return True, access_token

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = setup_browser()
    if not driver:
        return
    try:
        driver.get(BASE_URL)
        wait = optimized_wait(driver)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logging.info(f"Login Attempt {attempt}/{MAX_ATTEMPTS}")
            if login_irctc(driver, wait):
                fill_train_search(driver)
                break
            else:
                logging.info("Retrying login (full page refresh)...")
                driver.refresh()
                wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText')))
        else:
            logging.warning("Reached maximum login attempts without success.")
        time.sleep(2)  # Optional: adjust based on need
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
