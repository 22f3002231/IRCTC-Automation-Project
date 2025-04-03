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

USERNAME = "punam7350"
PASSWORD = "Theearthian@1"
FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION = "TATANAGAR JN - TATA (TATANAGAR)"
JOURNEY_DATE = "25/04/2025"
JOURNEY_QUOTA = "1A"
JOURNEY_TRAIN = "12101"
JOURNEY_CLASS = "1A"


# Passenger and Mobile Number Configuration
PASSENGERS = [
    {"name": "jhon", "age": "30", "gender": "M", "nationality": "IN", "berth": "LB"},
    {"name": "Jane Doe", "age": "28", "gender": "F", "nationality": "IN", "berth": "UB"},
    # Add more passengers as needed
]
MOBILE_NUMBER = "8668967041"

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

def add_passenger_forms(page, num_passengers):
    passenger_panel = page.locator("div.ui-panel:has-text('Passenger Details')")
    passenger_forms = passenger_panel.locator("app-passenger")
    current_forms = passenger_forms.count()
    print(f"Current number of passenger forms: {current_forms}")
    
    additional_forms_needed = num_passengers - current_forms
    if additional_forms_needed > 0:
        for i in range(additional_forms_needed):
            page.locator("a:has-text('+ Add Passenger')").click()
            page.wait_for_selector(f"app-passenger >> nth={current_forms + i}", timeout=5000)
            print("Added a passenger form.")

def fill_passenger_details(page, passengers):
    passenger_panel = page.locator("div.ui-panel:has-text('Passenger Details')")
    passenger_forms = passenger_panel.locator("app-passenger")
    
    for i, passenger in enumerate(passengers):
        passenger_form = passenger_forms.nth(i)
        name_field = passenger_form.locator("p-autocomplete input")
        
        # Ensure element is visible and wait for it
        name_field.scroll_into_view_if_needed()
        name_field.fill(passenger["name"])
        
        passenger_form.locator("input[formcontrolname='passengerAge']").fill(passenger["age"])
        passenger_form.locator("select[formcontrolname='passengerGender']").select_option(value=passenger["gender"])
        passenger_form.locator("select[formcontrolname='passengerNationality']").select_option(value=passenger["nationality"])
        passenger_form.locator("select[formcontrolname='passengerBerthChoice']").select_option(value=passenger["berth"])

def fill_mobile_number(page, mobile_number):
    """Fill the mobile number field, clearing any pre-filled value first."""
    try:
        mobile_field = page.locator("#mobileNumber")
        mobile_field.scroll_into_view_if_needed()
        
        # Check if the field has a value and clear it
        if mobile_field.input_value() != "":
            mobile_field.fill("")
        
        mobile_field.fill(mobile_number)
        page.wait_for_load_state('domcontentloaded', timeout=5000)
    except Exception as e:
        logging.error(f"Failed to fill mobile number: {e}")

def check_preferences(page):
    """Check the preferences checkboxes with explicit checks and JS clicks."""
    try:
        # Locate the "Other Preferences" panel
        preferences_panel = page.locator("div.ui-panel:has-text('Other Preferences')")
        
        # Check if the panel is expanded using aria-hidden attribute
        content_wrapper = preferences_panel.locator(".ui-panel-content-wrapper")
        is_expanded = content_wrapper.get_attribute("aria-hidden") == "false"
        
        if not is_expanded:
            # Click to expand the panel
            preferences_panel.locator(".ui-panel-titlebar-icon").click()
            page.wait_for_selector("#autoUpgradation", state="visible", timeout=15000)
        
        # Use JavaScript to click checkboxes to bypass potential issues
        auto_upgrade_script = """document.getElementById('autoUpgradation').click()"""
        confirm_berths_script = """document.getElementById('confirmberths').click()"""
        
        page.evaluate(auto_upgrade_script)
        page.evaluate(confirm_berths_script)
        
        print("Preferences checkboxes selected successfully.")
    except Exception as e:
        logging.error(f"Failed to select preferences: {e}")



def select_payment_method(page):
    """Select BHIM/UPI using precise XPath selector."""
    try:
        # XPath targeting the specific radio button by text and structure
        xpath = '//tr[contains(@class, "ng-star-inserted")]//label[contains(., "BHIM/UPI")]//div[@role="radio"]'
        
        # Wait for and click the element
        page.wait_for_selector(f"xpath={xpath}", state="visible", timeout=10000)
        page.locator(f"xpath={xpath}").click()
        
        # Verify active state
        page.wait_for_selector(
            f"xpath={xpath}[contains(@class, 'ui-state-active')]",
            timeout=5000
        )
        logging.info("BHIM/UPI payment successfully selected")
        
    except Exception as e:
        logging.error(f"Payment selection failed: {e}")









def submit_passanger_details(page):
    """Submit the form by clicking the Continue button."""
    try:
        continue_button = page.locator("button.train_Search.btnDefault:has-text('Continue')")
        continue_button.scroll_into_view_if_needed()
        continue_button.click()
        page.wait_for_load_state('domcontentloaded', timeout=100000)
    except Exception as e:
        logging.error(f"Failed to submit form: {e}")






def handle_captcha_and_proceed(page):
    """Handle CAPTCHA with network success detection and proper scrolling."""
    try:
        # Set up network monitoring before CAPTCHA interaction
        with page.expect_response(
            lambda response: 
                "/captchaverify/" in response.url and
                response.status == 200 and
                "SUCCESS" in response.text(),
            timeout=120000
        ) as response_info:
            
            # Scroll directly to CAPTCHA input
            captcha_input = page.wait_for_selector("#captcha", timeout=150000)
            captcha_input.scroll_into_view_if_needed()
            
            # Add visual instructions
            print("\n" + "="*50)
            print("MANUAL ACTION REQUIRED:")
            print("1. Solve the CAPTCHA in the visible browser window")
            print("2. Page will auto-proceed after correct entry")
            print("="*50 + "\n")
            
            # Wait for network confirmation
            response = response_info.value
            if response.ok:
                print("CAPTCHA verified successfully via network response!")
                return True

        return False

    except Exception as e:
        logging.error(f"CAPTCHA handling failed: {e}")
        return False











def select_bhim_and_pay(page):
    """Execute payment steps using verified working selectors."""
    try:
        # Click on the BHIM/UPI/USSD option
        bhim_selector = 'text=BHIM/ UPI/ USSD'
        page.wait_for_selector(bhim_selector, state="visible", timeout=15000)
        page.click(bhim_selector)
        logging.info("Clicked BHIM/UPI/USSD option")

        # Click Paytm option
        paytm_selector = 'text=Pay using BHIM (Powered by PAYTM ) also accepts UPI'
        page.wait_for_selector(paytm_selector, state="visible", timeout=15000)
        page.click(paytm_selector)
        logging.info("Clicked Paytm option")

        # Wait for UI stabilization
        page.wait_for_timeout(100)

        # Use the verified working selector
        pay_button_selector = 'button.btn.btn-primary:has-text("Pay & Book")'
        page.wait_for_selector(pay_button_selector, state="visible", timeout=5000)
        page.click(pay_button_selector)
        logging.info(f"Clicked Pay & Book using selector: {pay_button_selector}")
        logging.info("Payment processed successfully (BHIM/UPI with PAYTM and Pay & Book clicked)!")
        
        return True

    except Exception as e:
        logging.error(f"Payment failed: {str(e)}")
        return False


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    playwright, browser, page = setup_browser()
    
    try:
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        
        if login_irctc(page):
            if fill_train_search(page):
                page.wait_for_selector("div.bull-back.border-all", timeout=10000)
                
                if direct_train_class_selection(page):
                    availability = check_availability(page)
                    if availability:
                        logging.info(f"Availability: {availability}")
                        if select_date_and_click_book_button(page):
                            logging.info("Proceeding with booking...")
                            page.wait_for_selector("#mobileNumber", timeout=10000)
                            add_passenger_forms(page, len(PASSENGERS))
                            fill_passenger_details(page, PASSENGERS)
                            fill_mobile_number(page, MOBILE_NUMBER)
                            check_preferences(page)
                            select_payment_method(page)
                            submit_passanger_details(page)
                            
                            if handle_captcha_and_proceed(page):
                                logging.info("Successfully passed CAPTCHA verification!")
                                # Navigate to payment page and handle payment
                                page.wait_for_selector("div.bank-type:has-text('BHIM/ UPI/ USSD')", timeout=15000)
                                if select_bhim_and_pay(page):
                                    logging.info("Payment processed successfully (BHIM/UPI with PAYTM and Pay & Book clicked)!")
                                else:
                                    logging.error("Payment processing failed")
                            else:
                                logging.error("CAPTCHA verification failed")

        time.sleep(5)
        
    except Exception as e:
        logging.error(f"Main error: {str(e)[:100]}")
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    main()