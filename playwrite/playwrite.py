import os
import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configuration (unchanged)
MAX_CAPTCHA_ATTEMPTS = 3
MAX_LOGIN_ATTEMPTS = 1
TIMEOUT = 5
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
            '--disable-extensions',
            '--disable-background-networking'
        ]
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        bypass_csp=True,
        java_script_enabled=True
    )
    page = context.new_page()
    return playwright, browser, page



def login_irctc(page):
    """Login with manual CAPTCHA (unchanged from working version)"""
    try:
        login_selector = "a[aria-label='Click here to Login in application']"
        page.wait_for_selector(login_selector, state="visible", timeout=15000)
        page.eval_on_selector(login_selector, "el => el.click()")
        
        page.wait_for_selector("input[formcontrolname='userid']", timeout=5000)
        page.evaluate("""([username, password]) => {
            const userInput = document.querySelector("input[formcontrolname='userid']");
            const passInput = document.querySelector("input[formcontrolname='password']");
            
            function setValue(element, value) {
                element.value = value;
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.dispatchEvent(new Event('blur', { bubbles: true }));
            }
            
            setValue(userInput, username);
            setValue(passInput, password);
        }""", [USERNAME, PASSWORD])

        page.wait_for_timeout(500)
        user_val = page.eval_on_selector("input[formcontrolname='userid']", "el => el.value")
        pass_val = page.eval_on_selector("input[formcontrolname='password']", "el => el.value")
        logging.info(f"Username field: {user_val}")
        logging.info(f"Password field: {pass_val[:2]}*** (masked)")

        print("\nPlease manually enter the CAPTCHA and click 'SIGN IN'.")
        print("The script will resume automatically after successful login.")
        
        with page.expect_response(
            lambda response: "webtoken" in response.url,
            timeout=60000
        ) as response_info:
            pass
        
        response = response_info.value
        data = response.json()
        
        if response.status == 200 and "access_token" in data:
            logging.info("Login successful!")
            return True
        
        logging.error("Login failed - no access token received")
        return False

    except PlaywrightTimeoutError:
        logging.error("Timeout waiting for manual login")
        return False
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        return False



def fill_train_search(page):
    """Fixed form filling with robust date handling"""
    try:
        logging.info("Starting train search form filling...")

        # From Station
        from_input = "p-autocomplete[formcontrolname='origin'] input"
        page.wait_for_selector(from_input, state="visible", timeout=TIMEOUT*1000)
        page.fill(from_input, FROM_STATION)
        page.eval_on_selector(from_input, """el => {
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""")
        logging.info(f"From station set: {FROM_STATION}")

        # To Station
        to_input = "p-autocomplete[formcontrolname='destination'] input"
        page.fill(to_input, TO_STATION)
        page.eval_on_selector(to_input, """el => {
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""")
        logging.info(f"To station set: {TO_STATION}")

        # Date - Using keyboard simulation
        date_input = "p-calendar[formcontrolname='journeyDate'] input"
        page.wait_for_selector(date_input, state="visible", timeout=TIMEOUT*1000)
        page.click(date_input)
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        page.type(date_input, JOURNEY_DATE)
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)  # Allow Angular to process
        
        # Verify date
        date_val = page.eval_on_selector(date_input, "el => el.value")
        logging.info(f"Date set to: {date_val}")

        # Quota
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
        logging.info(f"Quota set to: {JOURNEY_QUOTA}")

        # Submit
        page.click("xpath=//button[contains(., 'Search')]", timeout=TIMEOUT*1000)
        logging.info("Search submitted successfully!")
        
    except Exception as e:
        logging.error(f"Search form error: {e}")
        page.screenshot(path="form_error.png")  # Debug screenshot



def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    playwright, browser, page = setup_browser()
    
    try:
        page.goto(BASE_URL, wait_until='domcontentloaded', timeout=15000)
        
        if login_irctc(page):
            fill_train_search(page)
        
        time.sleep(5)
        
    except Exception as e:
        logging.error(f"Main error: {e}")
    finally:
        browser.close()
        playwright.stop()



if __name__ == "__main__":
    main()