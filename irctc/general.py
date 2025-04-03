import os
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration
MAX_CAPTCHA_ATTEMPTS = 3
MAX_LOGIN_ATTEMPTS = 1
BASE_URL = "https://www.irctc.co.in/nget/train-search"

USERNAME = "punam7350"
PASSWORD = "Theearthian@1"
FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION = "TATANAGAR JN - TATA (TATANAGAR)"
JOURNEY_DATE = "25/04/2025"
JOURNEY_QUOTA = "1A"
JOURNEY_TRAIN = "12101"
JOURNEY_CLASS = "1A"
UPI_ID = "8668967041@ybl"

PASSENGERS = [
    {"name": "jhon", "age": "30", "gender": "M", "nationality": "IN", "berth": "LB"},
    {"name": "Jane Doe", "age": "28", "gender": "F", "nationality": "IN", "berth": "UB"},
]
MOBILE_NUMBER = "8668967041"

def setup_browser():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=False,
        args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage', 
              '--disable-extensions', '--disable-background-networking']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        bypass_csp=True,
        java_script_enabled=True,
        service_workers="block",
    )
    return playwright, browser, context.new_page()

def login_irctc(page):
    try:
        page.wait_for_selector("a[aria-label='Click here to Login in application']").click()
        page.wait_for_selector("input[formcontrolname='userid']")
        
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
        with page.expect_response(lambda r: "webtoken" in r.url):
            pass
        return page.query_selector("button.ng-tns-c19-3") is None
    except Exception as e:
        logging.error(f"Login failed: {e}")
        return False

def fill_train_search(page):
    try:
        page.wait_for_selector("p-autocomplete[formcontrolname='origin'] input").fill(FROM_STATION)
        page.fill("p-autocomplete[formcontrolname='destination'] input", TO_STATION)
        
        date_input = page.wait_for_selector("p-calendar[formcontrolname='journeyDate'] input")
        date_input.click()
        date_input.press("Control+a")
        date_input.press("Backspace")
        date_input.type(JOURNEY_DATE)
        date_input.press("Escape")
        
        page.evaluate("""(quota) => {
            document.querySelector("p-dropdown[formcontrolname='journeyQuota']").value = quota;
        }""", JOURNEY_QUOTA)
        
        page.click("button:has-text('Search')")
        return True
    except Exception as e:
        logging.error(f"Search form error: {e}")
        return False

def direct_train_class_selection(page):
    try:
        target_selector = (
            f"div.bull-back:has-text('({JOURNEY_TRAIN})') "
            f"div.pre-avl:has-text('{JOURNEY_CLASS}')"
        )
        element = page.wait_for_selector(target_selector)
        element.scroll_into_view_if_needed()
        element.click()
        page.wait_for_selector(f"{target_selector} .link")
        return True
    except Exception as e:
        logging.error(f"Direct selection failed: {e}")
        return False

def check_availability(page):
    try:
        status_selector = (
            f"div.bull-back:has-text('({JOURNEY_TRAIN})') "
            f"div.pre-avl:has-text('{JOURNEY_CLASS}') .link"
        )
        status_element = page.wait_for_selector(status_selector)
        return status_element.inner_text().strip()
    except Exception as e:
        logging.error(f"Availability check failed: {e}")
        return None

def wait_until_8am_with_millisecond_precision():
    """Wait until exactly 8:00:00.000 AM with millisecond precision."""
    now = datetime.now()
    target = datetime(now.year, now.month, now.day, 8, 0, 0, 0)  # 8:00:00.000
    
    if now >= target:
        logging.info("Current time is past 8 AM, proceeding immediately")
        return
    
    # Convert to seconds with millisecond precision
    seconds_to_wait = (target - now).total_seconds()
    logging.info(f"Waiting {seconds_to_wait:.3f} seconds until 8:00:00.000 AM")
    
    # Use perf_counter for high-precision timing
    start_time = time.perf_counter()
    while (time.perf_counter() - start_time) < seconds_to_wait:
        time.sleep(0.001)  # Sleep in 1ms increments for precision
    
    # Fine-tune to hit exactly 8:00:00.000
    while datetime.now() < target:
        pass  # Busy wait for the last few microseconds
    
    logging.info(f"Reached 8:00:00.000 AM, current time: {datetime.now().strftime('%H:%M:%S.%f')}")

def select_date_and_click_book_button(page):
    """Wait until 8 AM with millisecond precision and retry clicking if disabled."""
    try:
        wait_until_8am_with_millisecond_precision()
        
        date_obj = datetime.strptime(JOURNEY_DATE, "%d/%m/%Y")
        formatted_date = date_obj.strftime("%a, %d %b")
        
        # Select date once before the retry loop
        date_selector = f"xpath=//div[contains(@class, 'pre-avl')]//strong[contains(., '{formatted_date}')]"
        page.wait_for_selector(date_selector, state="visible").click()
        logging.info(f"Selected date: {formatted_date}")
        
        book_button_selector = "xpath=//button[contains(@class, 'btnDefault') and contains(., 'Book Now') and not(contains(@class, 'disable-book'))]"
        book_button = page.wait_for_selector(book_button_selector, state="visible")
        
        # Click at exactly 8 AM and retry if disabled
        while True:
            try:
                if not book_button.is_disabled():
                    book_button.click()
                    logging.info("Clicked 'Book Now' button successfully!")
                    return True
                else:
                    logging.warning("Book Now button is disabled, retrying in 10ms...")
                    time.sleep(0.01)  # Retry every 10ms
            except Exception as e:
                logging.warning(f"Retry attempt failed: {e}, retrying in 10ms...")
                time.sleep(0.01)
                
    except Exception as e:
        logging.error(f"Failed to click 'Book Now': {e}")
        return False

def add_passenger_forms(page, num_passengers):
    passenger_panel = page.locator("div.ui-panel:has-text('Passenger Details')")
    passenger_forms = passenger_panel.locator("app-passenger")
    current_forms = passenger_forms.count()
    
    for _ in range(num_passengers - current_forms):
        page.locator("a:has-text('+ Add Passenger')").click()
        page.wait_for_selector(f"app-passenger >> nth={current_forms}")

def fill_passenger_details(page, passengers):
    passenger_panel = page.locator("div.ui-panel:has-text('Passenger Details')")
    passenger_forms = passenger_panel.locator("app-passenger")
    
    for i, passenger in enumerate(passengers):
        form = passenger_forms.nth(i)
        form.locator("p-autocomplete input").fill(passenger["name"])
        form.locator("input[formcontrolname='passengerAge']").fill(passenger["age"])
        form.locator("select[formcontrolname='passengerGender']").select_option(value=passenger["gender"])
        form.locator("select[formcontrolname='passengerNationality']").select_option(value=passenger["nationality"])
        form.locator("select[formcontrolname='passengerBerthChoice']").select_option(value=passenger["berth"])

def fill_mobile_number(page, mobile_number):
    try:
        mobile_field = page.locator("#mobileNumber")
        mobile_field.scroll_into_view_if_needed()
        if mobile_field.input_value():
            mobile_field.fill("")
        mobile_field.fill(mobile_number)
    except Exception as e:
        logging.error(f"Failed to fill mobile number: {e}")

def check_preferences(page):
    try:
        panel = page.locator("div.ui-panel:has-text('Other Preferences')")
        if panel.locator(".ui-panel-content-wrapper").get_attribute("aria-hidden") != "false":
            panel.locator(".ui-panel-titlebar-icon").click()
            page.wait_for_selector("#autoUpgradation")
        
        page.evaluate("document.getElementById('autoUpgradation').click()")
        page.evaluate("document.getElementById('confirmberths').click()")
        print("Preferences selected.")
    except Exception as e:
        logging.error(f"Failed to select preferences: {e}")

def select_payment_method(page):
    try:
        xpath = '//tr[contains(@class, "ng-star-inserted")]//label[contains(., "BHIM/UPI")]//div[@role="radio"]'
        page.wait_for_selector(f"xpath={xpath}").click()
        page.wait_for_selector(f"xpath={xpath}[contains(@class, 'ui-state-active')]")
        logging.info("BHIM/UPI selected")
    except Exception as e:
        logging.error(f"Payment selection failed: {e}")

def submit_passanger_details(page):
    try:
        page.locator("button.train_Search.btnDefault:has-text('Continue')").click()
    except Exception as e:
        logging.error(f"Failed to submit form: {e}")

def handle_captcha_and_proceed(page):
    try:
        with page.expect_response(
            lambda r: "/captchaverify/" in r.url and r.status == 200 and "SUCCESS" in r.text()
        ) as response_info:
            captcha_input = page.wait_for_selector("#captcha")
            captcha_input.scroll_into_view_if_needed()
            print("\n" + "="*50)
            print("MANUAL ACTION REQUIRED:")
            print("1. Solve the CAPTCHA")
            print("2. Page will auto-proceed")
            print("="*50 + "\n")
            response = response_info.value
            if response.ok:
                print("CAPTCHA verified!")
                return True
        return False
    except Exception as e:
        logging.error(f"CAPTCHA failed: {e}")
        return False

def select_bhim_and_pay(page):
    try:
        page.wait_for_selector('text=BHIM/ UPI/ USSD').click()
        page.wait_for_selector('text=Pay using BHIM (Powered by PAYTM ) also accepts UPI').click()
        page.wait_for_selector('button.btn.btn-primary:has-text("Pay & Book")').click()
        page.wait_for_url(lambda url: "secure.paytmpayments.com/theia/processTransaction" in url)
        handle_paytm_upi_payment(page)
        return True
    except Exception as e:
        logging.error(f"Payment failed: {e}")
        return False

def handle_paytm_upi_payment(page):
    try:
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("input[type='radio'][value='upi']").click()
        vpa_field = page.wait_for_selector("input[placeholder='Enter VPA']")
        if vpa_field.input_value():
            page.fill("input[placeholder='Enter VPA']", "")
        page.fill("input[placeholder='Enter VPA']", UPI_ID)
        page.wait_for_selector("button.btn.btn-primary.w100").click()
        logging.info("Payment initiated - check UPI app")
    except Exception as e:
        logging.error(f"UPI payment failed: {e}")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    playwright, browser, page = setup_browser()
    
    try:
        page.goto(BASE_URL, wait_until="domcontentloaded")
        if login_irctc(page) and fill_train_search(page):
            page.wait_for_selector("div.bull-back.border-all")
            if direct_train_class_selection(page):
                availability = check_availability(page)
                if availability:
                    logging.info(f"Availability: {availability}")
                    if select_date_and_click_book_button(page):
                        page.wait_for_selector("#mobileNumber")
                        add_passenger_forms(page, len(PASSENGERS))
                        fill_passenger_details(page, PASSENGERS)
                        fill_mobile_number(page, MOBILE_NUMBER)
                        check_preferences(page)
                        select_payment_method(page)
                        submit_passanger_details(page)
                        if handle_captcha_and_proceed(page):
                            page.wait_for_selector("div.bank-type:has-text('BHIM/ UPI/ USSD')")
                            if select_bhim_and_pay(page):
                                logging.info("Payment completed!")
        
        print("\n" + "="*50)
        print("SCRIPT COMPLETED")
        print("Check browser window")
        print("="*50 + "\n")
        time.sleep(30)
        
    except Exception as e:
        logging.error(f"Main error: {str(e)[:100]}")
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    main()