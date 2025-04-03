import os
import time
import logging
from datetime import datetime
import requests  # For making API calls

# Import Selenium Wire’s webdriver instead of the standard Selenium webdriver
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException

from captcha_solver import solve_captcha  # Your CAPTCHA solving module

# ----------------------------------
# Configuration
# ----------------------------------
MAX_ATTEMPTS = 3
TIMEOUT = 10              # seconds for main explicit waits
FEEDBACK_TIMEOUT = 3      # shorter wait for login feedback after sign in
BASE_URL = "https://www.irctc.co.in/nget/train-search"

USERNAME = "punam7350"
PASSWORD = "Theearthian@1"

# Example station strings (adjust these if needed)
FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION   = "TATANAGAR JN - TATA (TATANAGAR)"
JOURNEY_DATE = "20/04/2025"  # in dd/mm/yyyy format

# For the train search POST payload, we are using sample codes.
DEFAULT_SRC_CODE = "HTE"    # Sample source station code
DEFAULT_DEST_CODE = "KYN"   # Sample destination station code
DEFAULT_QUOTA_CODE = "GN"   # Sample quota code for GENERAL

# ----------------------------------

def setup_browser():
    options = Options()
    options.page_load_strategy = 'eager'
    # Uncomment the next line to run headless if desired:
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

import json

def capture_access_token(driver):
    """
    Iterate over intercepted requests to capture the web token from the
    /authprovider/webtoken endpoint.
    """
    access_token = None
    for request in driver.requests:
        if "authprovider/webtoken" in request.url and request.response:
            try:
                # Decode the raw response body and parse the JSON.
                token_data = json.loads(request.response.body.decode('utf-8'))
                access_token = token_data.get("access_token")
                if access_token:
                    logging.info(f"Captured access token: {access_token}")
                    return access_token
            except Exception as e:
                logging.error(f"Error parsing token from request: {e}")
    logging.error("Access token not found!")
    return None


def handle_captcha(driver, wait):
    """
    Wait for the captcha image to load, solve it using solve_captcha(),
    and fill in the captcha input field.
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

def login_irctc(driver, wait):
    try:
        # Click the login button once
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText'))).click()
        
        # Fill in username and password using JavaScript injection.
        login_js = """
        var username = arguments[0];
        var password = arguments[1];
        var user_input = document.querySelector("input[formcontrolname='userid']");
        var pass_input = document.querySelector("input[formcontrolname='password']");
        if(user_input){
          user_input.value = username;
          user_input.dispatchEvent(new Event('input', { bubbles: true }));
          user_input.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if(pass_input){
          pass_input.value = password;
          pass_input.dispatchEvent(new Event('input', { bubbles: true }));
          pass_input.dispatchEvent(new Event('change', { bubbles: true }));
        }
        return true;
        """
        driver.execute_script(login_js, USERNAME, PASSWORD)
        
        # Handle captcha (retry up to MAX_ATTEMPTS times)
        captcha_attempts = 0
        while captcha_attempts < MAX_ATTEMPTS:
            captcha_attempts += 1
            if not handle_captcha(driver, wait):
                logging.warning("Captcha not loaded or solved; waiting for refresh...")
                time.sleep(1)
                continue
            # Click SIGN IN button
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'SIGN IN')]"))).click()
            time.sleep(0.5)  # Brief pause to check for login feedback

            try:
                feedback_wait = WebDriverWait(driver, FEEDBACK_TIMEOUT)
                element = feedback_wait.until(EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//a[@routerlink='/logout']")),
                    EC.visibility_of_element_located((By.XPATH, "//div[contains(@class, 'loginError')]"))
                ))
                if element.tag_name.lower() == 'a' and element.get_attribute('routerlink') == '/logout':
                    logging.info("Login successful!")
                    return True
                else:
                    logging.info("Invalid captcha; retrying captcha solve...")
                    cap_input = driver.find_element(By.ID, "captcha")
                    cap_input.clear()
                    time.sleep(0.5)
            except TimeoutException:
                logging.info("Timeout waiting for login feedback; retrying captcha...")
        return False
    except (NoSuchElementException, TimeoutException, ElementNotInteractableException) as e:
        logging.error(f"Login error: {e}")
        return False

def search_trains_tc(driver):
    """
    After successful login, capture the access token from intercepted network
    traffic and use it in the POST request to search for trains via the TC endpoint.
    """
    try:
        # Capture the access token using Selenium Wire
        access_token = capture_access_token(driver)
        if not access_token:
            logging.error("Could not capture access token; aborting API call.")
            return
        
        sess = requests.Session()
        # (Optional) Transfer cookies if needed
        for cookie in driver.get_cookies():
            sess.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
        
        # Set headers to mimic the browser, including the captured token.
        sess.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": "https://www.irctc.co.in",
            "Referer": "https://www.irctc.co.in/nget/train-search",
            "Authorization": f"Bearer {access_token}"
        })
        
        # Convert journey date from dd/mm/yyyy to yyyymmdd.
        try:
            jrny_date = datetime.strptime(JOURNEY_DATE, "%d/%m/%Y").strftime("%Y%m%d")
        except Exception as e:
            logging.error(f"Date conversion error: {e}")
            jrny_date = JOURNEY_DATE  # fallback
        
        # Build JSON payload as observed from the network.
        payload = {
            "concessionBooking": False,
            "srcStn": DEFAULT_SRC_CODE,       # e.g. "HTE"
            "destStn": DEFAULT_DEST_CODE,       # e.g. "KYN"
            "jrnyClass": "",                  # Empty as per sample
            "jrnyDate": jrny_date,            # e.g. "20250420"
            "quotaCode": DEFAULT_QUOTA_CODE,    # e.g. "GN"
            "currentBooking": "false",        # Note: value as string per sample
            "flexiFlag": False,
            "handicapFlag": False,
            "ticketType": "E",
            "loyaltyRedemptionBooking": False,
            "ftBooking": False
        }
        
        search_url = "https://www.irctc.co.in/eticketing/protected/mapps1/altAvlEnq/TC"
        logging.info(f"Posting train search request to {search_url} with payload: {payload}")
        response = sess.post(search_url, json=payload)
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Train search response: {data}")
        else:
            logging.error(f"Failed to search trains: HTTP {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error in search_trains_tc: {e}")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = setup_browser()
    if not driver:
        return
    try:
        driver.get(BASE_URL)
        wait = WebDriverWait(driver, TIMEOUT)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logging.info(f"Login Attempt {attempt}/{MAX_ATTEMPTS}")
            if login_irctc(driver, wait):
                # After successful login, use Selenium Wire to capture the token and perform the POST search.
                search_trains_tc(driver)
                break
            else:
                logging.info("Retrying login (full page refresh)...")
                driver.refresh()
                wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText')))
        else:
            logging.warning("Reached maximum login attempts without success.")
        time.sleep(10)  # Optional: adjust based on need
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
