import os
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configuration
MAX_CAPTCHA_ATTEMPTS = 3
MAX_LOGIN_ATTEMPTS = 1
TIMEOUT = 5  # seconds (for selectors, multiplied by 1000 for ms)
BASE_URL = "https://www.irctc.co.in/nget/train-search"

USERNAME = "rohit_7350"
PASSWORD = "Theearthian@1"
FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION = "TATANAGAR JN - TATA (TATANAGAR)"
JOURNEY_DATE = "20/04/2025"
JOURNEY_QUOTA = "SLEEPER"
JOURNEY_TRAIN = "12859"
JOURNEY_CLASS = "SL"

def setup_browser():
    """Initialize optimized Playwright browser instance."""
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
        java_script_enabled=True,
        service_workers="block",
    )
    page = context.new_page()
    return playwright, browser, page

def login_irctc(page):
    """Optimized login with direct element access using simulated events."""
    try:
        # Click the login link after ensuring it's visible
        page.wait_for_selector("a[aria-label='Click here to Login in application']", timeout=15000).click()
        
        # Wait for the username input to be available
        page.wait_for_selector("input[formcontrolname='userid']", timeout=5000)
        
        # Set values with simulated events similar to manual user input
        page.evaluate(
            """([username, password]) => {
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
               }""",
            [USERNAME, PASSWORD]
        )
        
        print("\nComplete CAPTCHA and SIGN IN manually")
        
        # Wait for network confirmation of login (e.g., webtoken in URL)
        with page.expect_response(lambda r: "webtoken" in r.url, timeout=60000):
            pass
            
        # Check login success by verifying if the expected button is absent
        return page.query_selector("button.ng-tns-c19-3") is None

    except Exception as e:
        logging.error(f"Login failed: {e}")
        return False

def fill_train_search(page):
    """Optimized form filling using direct selectors."""
    try:
        # From Station
        page.wait_for_selector("p-autocomplete[formcontrolname='origin'] input").fill(FROM_STATION)
        
        # To Station
        page.fill("p-autocomplete[formcontrolname='destination'] input", TO_STATION)

        # Date handling with keyboard shortcuts
        date_input = page.wait_for_selector("p-calendar[formcontrolname='journeyDate'] input")
        date_input.click()
        date_input.press("Control+a")
        date_input.press("Backspace")
        date_input.type(JOURNEY_DATE)
        date_input.press("Escape")

        # Quota selection
        page.evaluate("""(quota) => {
            document.querySelector("p-dropdown[formcontrolname='journeyQuota']").value = quota;
        }""", JOURNEY_QUOTA)

        # Submit search
        page.click("button:has-text('Search')")
        return True
        
    except Exception as e:
        logging.error(f"Search form error: {e}")
        return False

def direct_train_class_selection(page):
    """Directly select train and class using combined CSS selector."""
    try:
        # Combined train+class selector
        target_selector = (
            f"div.bull-back:has-text('({JOURNEY_TRAIN})') "  # Train container
            f"div.pre-avl:has-text('{JOURNEY_CLASS}')"        # Class element
        )

        # Wait for and click target element
        element = page.wait_for_selector(target_selector, timeout=15000)
        element.scroll_into_view_if_needed()
        element.click()
        
        # Wait for availability load
        page.wait_for_selector(f"{target_selector} .link", timeout=5000)
        return True
        
    except Exception as e:
        logging.error(f"Direct selection failed: {e}")
        return False

def check_availability(page):
    """Check availability status using direct CSS selection."""
    try:
        # Get status from already selected element
        status_selector = (
            f"div.bull-back:has-text('({JOURNEY_TRAIN})') "
            f"div.pre-avl:has-text('{JOURNEY_CLASS}') .link"
        )
        status_element = page.wait_for_selector(status_selector, timeout=5000)
        availability = status_element.inner_text().strip()
        
        return availability  # Return only availability, no booking readiness check here
        
    except Exception as e:
        logging.error(f"Availability check failed: {e}")
        return None

def select_date_and_click_book_button(page, max_attempts=5):
    """Select the required date from the availability table and click 'Book Now' if clickable, with retries."""
    attempt = 0
    while attempt < max_attempts:
        try:
            # Convert JOURNEY_DATE (dd/mm/yyyy) to match HTML format (e.g., "Fri, 25 Apr")
            date_obj = datetime.strptime(JOURNEY_DATE, "%d/%m/%Y")
            formatted_date = date_obj.strftime("%a, %d %b")  # e.g., "Fri, 25 Apr"

            # Find and select the required date in the availability table
            date_selector = f"xpath=//div[contains(@class, 'pre-avl')]//strong[contains(., '{formatted_date}')]"
            date_element = page.wait_for_selector(date_selector, state="visible", timeout=TIMEOUT*2000)
            date_element.click()
            logging.info(f"Selected date: {formatted_date}")

            # Wait for the page to update after date selection
            page.wait_for_selector("xpath=.//div[contains(@class, 'pre-avl') and contains(@class, 'selected-class')]//strong", state="visible", timeout=TIMEOUT*2000)

            # Check if the "Book Now" button is clickable (no 'disable-book' class and enabled)
            book_button_selector = "xpath=//button[contains(@class, 'btnDefault') and contains(., 'Book Now') and not(contains(@class, 'disable-book'))]"
            page.wait_for_selector(book_button_selector, state="visible", timeout=TIMEOUT*2000)
            
            # Use is_disabled() instead of is_enabled() for buttons, or check the class directly
            book_button = page.locator(book_button_selector)
            if not book_button.is_disabled(timeout=TIMEOUT*1000):  # Check if not disabled
                book_button.click(timeout=TIMEOUT*2000)
                logging.info("Clicked 'Book Now' button successfully!")
                return True
            else:
                logging.warning("Book Now button is not clickable yet. Retrying...")
                attempt += 1
                time.sleep(2)  # Wait before retrying
                continue  # Retry the process

        except Exception as e:
            logging.error(f"Error in selecting date or clicking 'Book Now' (attempt {attempt + 1}/{max_attempts}): {e}")
            attempt += 1
            time.sleep(2)  # Wait before retrying
            continue

    logging.error(f"Failed to click 'Book Now' after {max_attempts} attempts.")
    return False

# --- Main flow demonstrating the new functionality ---

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    playwright, browser, page = setup_browser()
    
    try:
        # Modified navigation with DOMContentLoaded
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        
        # Rest of the code remains the same
        if login_irctc(page):
            if fill_train_search(page):
                page.wait_for_selector("div.bull-back.border-all", timeout=10000)
                
                if direct_train_class_selection(page):
                    availability = check_availability(page)
                    if availability:
                        logging.info(f"Availability: {availability}")
                        # Select date and attempt to click 'Book Now'
                        if select_date_and_click_book_button(page):
                            logging.info("Proceeding with booking process...")
                        else:
                            logging.warning("Failed to complete booking process.")
                    else:
                        logging.error("Failed to get availability.")

        time.sleep(5)
        
    except Exception as e:
        logging.error(f"Main error: {e}")
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    main()