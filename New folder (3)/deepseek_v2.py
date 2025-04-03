import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from captcha_solver import solve_captcha  # Ensure this is optimized

# Configuration constants
MAX_ATTEMPTS = 3
TIMEOUT = 10  # Reduced from 30 seconds
BASE_URL = 'https://www.irctc.co.in/nget/train-search'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_browser(headless=False):  # Default to headless for speed
    options = Options()
    options.page_load_strategy = 'eager'  # Faster page loading
    if headless:
        options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # Error handling for driver setup
    try:
        service = Service(executable_path=r'C:\Windows\chromedriver.exe')
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logging.error(f"Browser setup failed: {e}")
        return None

def optimized_wait(driver):
    return WebDriverWait(driver, TIMEOUT)

def handle_captcha(driver, wait):
    captcha_img = wait.until(EC.visibility_of_element_located(
        (By.XPATH, "//app-captcha//img[contains(@class, 'captcha-img')]")
    ))
    
    # Direct base64 processing without file save
    base64_data = captcha_img.get_attribute("src").split(",", 1)[-1]
    captcha_text = solve_captcha(base64_data)  # Modify solver to accept base64
    
    if not captcha_text or len(captcha_text) < 4:
        logging.warning("Invalid CAPTCHA solution")
        return None
        
    captcha_input = wait.until(EC.visibility_of_element_located((By.ID, 'captcha')))
    captcha_input.clear()
    captcha_input.send_keys(captcha_text)
    return captcha_text

def login_attempt(driver, wait):
    # Fill credentials
    username = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='User Name']")))
    password = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Password']")))
    
    username.clear()
    username.send_keys("punam7350")
    password.clear()
    password.send_keys("Theearthian@1")

    # Handle CAPTCHA
    captcha_text = handle_captcha(driver, wait)
    if not captcha_text:
        return False

    # Submit form
    submit_button = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[contains(., 'SIGN IN')]")
    ))
    submit_button.click()
    
    # Check for login success by waiting for the logout element or an error message
    try:
        element = wait.until(EC.any_of(
            EC.presence_of_element_located((By.XPATH, "//a[@routerlink='/logout']")),
            EC.visibility_of_element_located((By.XPATH, "//span[contains(., 'Invalid Captcha')]"))
        ))
        # If the found element is the logout element, login succeeded
        if element.tag_name.lower() == 'a' and element.get_attribute('routerlink') == '/logout':
            return True
        else:
            return False
    except TimeoutException:
        return False

def interact_with_irctc():
    driver = setup_browser()
    if not driver:
        return

    try:
        driver.get(BASE_URL)
        wait = optimized_wait(driver)

        # Initiate login by clicking the login button
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText'))).click()
        
        # Main login loop
        for attempt in range(1, MAX_ATTEMPTS + 1):
            logging.info(f"Attempt {attempt}/{MAX_ATTEMPTS}")
            if login_attempt(driver, wait):
                logging.info("Login successful!")
                return  # Exit on success
                
            logging.info("Retrying...")
            driver.refresh()  # Force refresh for new CAPTCHA
            wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText'))).click()

        logging.warning("Maximum attempts reached")

    except Exception as e:
        logging.error(f"Critical error: {e}")
        driver.save_screenshot('error.png')
    finally:
        driver.quit()

if __name__ == "__main__":
    interact_with_irctc()
