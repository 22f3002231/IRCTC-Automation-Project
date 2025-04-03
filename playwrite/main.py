import os
import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from captcha_solver import solve_captcha

# Configuration - Adjusted timeouts
MAX_CAPTCHA_ATTEMPTS = 3
MAX_LOGIN_ATTEMPTS = 1
TIMEOUT = 5  # Reduced from 10s to 5s
BASE_URL = "https://www.irctc.co.in/nget/train-search"

USERNAME = "punam7350"
PASSWORD = "Theearthian@1"
FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION = "TATANAGAR JN - TATA (TATANAGAR)"
JOURNEY_DATE = "20/04/2025"
JOURNEY_CLASS = ""
JOURNEY_QUOTA = "SLEEPER"

def setup_browser():
    """Initialize Playwright browser with performance optimizations"""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=False,
        args=[
            '--disable-gpu',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-extensions',  # Added to reduce startup time
            '--disable-background-networking'  # Reduce background tasks
        ]
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        bypass_csp=True,  # Speed up by bypassing CSP checks
        java_script_enabled=True
    )
    page = context.new_page()
    return playwright, browser, page





def handle_captcha(page):
    """Solve CAPTCHA with enhanced error handling"""
    try:
        # Wait for CAPTCHA image to refresh
        captcha_img = page.wait_for_selector(
            "xpath=//app-captcha//img[contains(@class, 'captcha-img')]", 
            state="visible",
            timeout=TIMEOUT*1000
        )
        
        # Get fresh CAPTCHA image
        captcha_src = captcha_img.get_attribute("src")
        if not captcha_src or len(captcha_src) < 50:
            logging.warning("Captcha image not loaded properly.")
            return None
            
        base64_data = captcha_src.split(",", 1)[-1]
        captcha_text = solve_captcha(base64_data)
        
        if not captcha_text or len(captcha_text) < 4:
            logging.warning("Invalid CAPTCHA solution")
            return None
            
        # Fill CAPTCHA input
        captcha_input = page.wait_for_selector("#captcha", state="visible")
        captcha_input.fill("")
        captcha_input.fill(captcha_text)
        return captcha_text
        
    except PlaywrightTimeoutError:
        logging.error("Timeout while handling CAPTCHA")
        return None
    except Exception as e:
        logging.error(f"CAPTCHA handling error: {e}")
        return None
    





def login_irctc(page):
    """Login using working JavaScript click method"""
    try:
        logging.info("Attempting to locate login button...")
        login_selector = "a[aria-label='Click here to Login in application']"
        
        logging.info("Waiting for login button...")
        page.wait_for_selector(login_selector, state="visible", timeout=30000)
        
        # Use working JS click
        logging.info("Performing JavaScript click...")
        page.eval_on_selector(login_selector, "el => el.click()")
        
        # Verify login form appears
        page.wait_for_selector("input[formcontrolname='userid']", timeout=10000)
        logging.info("Login form visible, proceeding with credentials")

        # Fill credentials
        page.evaluate("""([username, password]) => {
            const userInput = document.querySelector("input[formcontrolname='userid']");
            const passInput = document.querySelector("input[formcontrolname='password']");
            
            function setAngularValue(element, value) {
                element.value = value;
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            setAngularValue(userInput, username);
            setAngularValue(passInput, password);
        }""", [USERNAME, PASSWORD])

        for attempt in range(MAX_CAPTCHA_ATTEMPTS):
            logging.info(f"CAPTCHA attempt {attempt+1}/{MAX_CAPTCHA_ATTEMPTS}")
            captcha_text = handle_captcha(page)
            if not captcha_text:
                continue

            try:
                with page.expect_response(
                    lambda response: "webtoken" in response.url,
                    timeout=TIMEOUT*1000
                ) as response_info:
                    page.wait_for_timeout(800)
                    page.click("xpath=//button[contains(., 'SIGN IN')]", force=True)

                response = response_info.value
                data = response.json()
                
                if response.status == 200 and "access_token" in data:
                    logging.info("Login successful!")
                    return True

                error_msg = data.get('error_description', '')
                logging.warning(f"Login failed: {error_msg}")
                
                page.fill("#captcha", "")
                if 'captcha' in error_msg.lower():
                    page.wait_for_selector(
                        "xpath=//app-captcha//img[contains(@class, 'captcha-img')]",
                        state="visible",
                        timeout=3000
                    )
                    continue
                return False

            except PlaywrightTimeoutError:
                logging.error("Login response timeout")
                if page.is_visible("input[formcontrolname='userid']", timeout=2000):
                    continue
                return False

        logging.error("All CAPTCHA attempts exhausted")
        return False

    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        return False







def fill_train_search(page):
    """Fill and submit search form with enhanced date handling"""
    try:
        # Station inputs
        page.evaluate("""([from_station, to_station]) => {
            document.querySelector("p-autocomplete[formcontrolname='origin'] input").value = from_station;
            document.querySelector("p-autocomplete[formcontrolname='destination'] input").value = to_station;
            
            const event = new Event('input', { bubbles: true });
            document.querySelectorAll('input').forEach(i => i.dispatchEvent(event));
        }""", [FROM_STATION, TO_STATION])

        # Enhanced date handling - simulate human interaction
        date_input_selector = "p-calendar[formcontrolname='journeyDate'] input"
        
        # Click into the date field
        page.click(date_input_selector)
        
        # Clear existing date (Ctrl+A and Delete)
        page.focus(date_input_selector)
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        
        # Type new date
        page.type(date_input_selector, JOURNEY_DATE)
        
        # Press Escape to close calendar and trigger update
        page.keyboard.press("Escape")
        
        # Add small delay to ensure Angular processes the change
        page.wait_for_timeout(500)

        # Verify date was set (for debugging)
        filled_date = page.eval_on_selector(date_input_selector, "el => el.value")
        logging.info(f"Date field value after setting: {filled_date}")

        # Quota selection
        quota_key = JOURNEY_QUOTA[0].lower()
        page.evaluate("""(key) => {
            const quotas = {'t': 'TATKAL', 'g': 'GENERAL', 'l': 'LADIES', 's': 'SLEEPER'};
            const selected = quotas[key] || 'GENERAL';
            
            const dropdown = document.querySelector("p-dropdown[formcontrolname='journeyQuota']");
            if(dropdown) {
                dropdown.querySelector('input').value = selected;
                dropdown.querySelector('.ui-dropdown-label').textContent = selected;
            }
        }""", quota_key)

        # Submit search
        page.click("xpath=//button[contains(., 'Search')]", timeout=TIMEOUT*1000)
        logging.info("Search submitted successfully!")
        
    except Exception as e:
        logging.error(f"Search form error: {e}")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    playwright, browser, page = setup_browser()
    
    try:
        logging.info("Navigating to IRCTC...")
        page.goto(BASE_URL, wait_until='domcontentloaded')
        logging.info(f"Page title: {page.title()}")
        
        if login_irctc(page):
            fill_train_search(page)
        else:
            logging.error("Login failed after retries")
            
        time.sleep(2)
        
    except Exception as e:
        logging.error(f"Main error: {e}")
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    main()







