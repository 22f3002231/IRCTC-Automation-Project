import os
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import cv2
import pytesseract
import numpy as np
import base64

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Configuration
MAX_CAPTCHA_ATTEMPTS = 5
TIMEOUT = 5  # seconds (for selectors, multiplied by 1000 for ms)
BASE_URL = "https://www.irctc.co.in/nget/train-search"

USERNAME = "punam7350"
PASSWORD = "Theearthian@1"
FROM_STATION = "KALYAN JN - KYN (MUMBAI)"
TO_STATION = "HATIA - HTE (HATIA/RANCHI)"
JOURNEY_DATE = "27/04/2025"
JOURNEY_QUOTA = "GENERAL"
JOURNEY_TRAIN = "12811"
JOURNEY_CLASS = "SL"
UPI_ID = "8668967041@ybl"

PASSENGERS = [ 
    {"name": "ROHITKUMAR SINGH", "age": "22", "gender": "M", "nationality": "IN", "berth": "UB"},
    {"name": "PUNAM DEVI", "age": "41", "gender": "F", "nationality": "IN", "berth": "LB"},
    {"name": "PAYAL ASHOK SINGH", "age": "19", "gender": "F", "nationality": "IN", "berth": "MB"},
    {"name": "NIKHIL KUMAR SINGH", "age": "12", "gender": "M", "nationality": "IN", "berth": "MB"},
    {"name": "JYOTI KUMARI", "age": "36", "gender": "F", "nationality": "IN", "berth": "LB"},
]

MOBILE_NUMBER = "8668967041"

def solve_captcha(base64_data):
    """Processes a base64 encoded CAPTCHA image and returns the solved text."""
    try:
        if 'base64,' in base64_data:
            base64_data = base64_data.split('base64,', 1)[-1]
        img_bytes = base64.b64decode(base64_data)
    except Exception as e:
        logging.error(f"Base64 decoding failed: {e}")
        return None

    np_array = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    if img is None:
        logging.error("Failed to decode image from base64 data")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()=,.?'
    text = pytesseract.image_to_string(cleaned, config=config).strip()
    logging.info(f"CAPTCHA solved: {text}")
    return text

def handle_captcha(page):
    """Solve CAPTCHA with enhanced error handling"""
    try:
        captcha_img = page.wait_for_selector(
            "xpath=//app-captcha//img[contains(@class, 'captcha-img')]", 
            state="visible",
            timeout=TIMEOUT*1000
        )
        
        captcha_src = captcha_img.get_attribute("src")
        if not captcha_src or len(captcha_src) < 50:
            logging.warning("Captcha image not loaded properly.")
            return None
            
        base64_data = captcha_src.split(",", 1)[-1]
        captcha_text = solve_captcha(base64_data)
        
        if not captcha_text or len(captcha_text) < 4:
            logging.warning("Invalid CAPTCHA solution")
            return None
            
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
    """Login using working JavaScript click method"""
    try:
        logging.info("Attempting to locate login button...")
        login_selector = "a[aria-label='Click here to Login in application']"
        
        logging.info("Waiting for login button...")
        page.wait_for_selector(login_selector, state="visible", timeout=30000)
        
        logging.info("Performing JavaScript click...")
        page.eval_on_selector(login_selector, "el => el.click()")
        
        page.wait_for_selector("input[formcontrolname='userid']", timeout=10000)
        logging.info("Login form visible, proceeding with credentials")

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
                page.click("button[aria-label='Click to refresh CAPTCHA']", timeout=2000)
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
                    page.click("button[aria-label='Click to refresh CAPTCHA']", timeout=2000)
                    continue
                return False

        logging.error("All CAPTCHA attempts exhausted")
        return False

    except Exception as e:
        logging.error(f"Login error: {str(e)}")
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
    now = datetime.now()
    target = datetime(now.year, now.month, now.day, 8, 0, 0, 0)
    
    if now >= target:
        logging.info("Current time is past 8 AM, proceeding immediately")
        return
    
    seconds_to_wait = (target - now).total_seconds()
    logging.info(f"Waiting {seconds_to_wait:.3f} seconds until 8:00:00.000 AM")
    
    start_time = time.perf_counter()
    while (time.perf_counter() - start_time) < seconds_to_wait:
        time.sleep(0.001)
    
    while datetime.now() < target:
        pass
    
    logging.info(f"Reached 8:00:00.000 AM, current time: {datetime.now().strftime('%H:%M:%S.%f')}")

def select_date_and_click_book_button(page):
    try:
        wait_until_8am_with_millisecond_precision()
        
        date_obj = datetime.strptime(JOURNEY_DATE, "%d/%m/%Y")
        formatted_date = date_obj.strftime("%a, %d %b")
        
        date_selector = f"xpath=//div[contains(@class, 'pre-avl')]//strong[contains(., '{formatted_date}')]"
        page.wait_for_selector(date_selector, state="visible").click()
        logging.info(f"Selected date: {formatted_date}")
        
        book_button_selector = "xpath=//button[contains(@class, 'btnDefault') and contains(., 'Book Now') and not(contains(@class, 'disable-book'))]"
        book_button = page.wait_for_selector(book_button_selector, state="visible")
        
        while True:
            try:
                if not book_button.is_disabled():
                    book_button.click()
                    logging.info("Clicked 'Book Now' button successfully!")
                    return True
                else:
                    logging.warning("Book Now button is disabled, retrying in 10ms...")
                    time.sleep(0.01)
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
    """Handle CAPTCHA after passenger details submission using provided HTML"""
    try:
        for attempt in range(MAX_CAPTCHA_ATTEMPTS):
            logging.info(f"CAPTCHA attempt {attempt+1}/{MAX_CAPTCHA_ATTEMPTS} after passenger details")
            
            # Use the same handle_captcha function but ensure it works with the HTML
            captcha_text = handle_captcha(page)
            if not captcha_text:
                page.click("xpath=//app-captcha//a[@aria-label='Click to refresh Captcha']", timeout=2000)
                continue

            # Submit CAPTCHA and wait for verification
            with page.expect_response(
                lambda r: "/captchaverify/" in r.url and r.status == 200,
                timeout=TIMEOUT*1000
            ) as response_info:
                page.click("button:has-text('Continue')", force=True)

            response = response_info.value
            if "SUCCESS" in response.text():
                logging.info("CAPTCHA verified successfully after passenger details!")
                return True

            logging.warning(f"CAPTCHA verification failed, retrying...")
            page.fill("#captcha", "")
            page.wait_for_selector(
                "xpath=//app-captcha//img[contains(@class, 'captcha-img')]",
                state="visible",
                timeout=3000
            )

        logging.error("Failed to solve CAPTCHA after all attempts")
        return False
    except Exception as e:
        logging.error(f"CAPTCHA handling failed after passenger details: {e}")
        return False

def select_bhim_and_pay(page):
    try:
        page.wait_for_selector('text=BHIM/ UPI/ USSD').click()
        page.wait_for_selector('text=Pay using BHIM (Powered by PAYTM ) also accepts UPI').click()
        page.wait_for_selector('button.btn.btn-primary:has-text("Pay & Book")').click()
        page.wait_for_url(lambda url: "secure.paytmpayments.com/theia/processTransaction" in url)
        logging.info("Reached Paytm UPI payment page - proceed manually")
        return True
    except Exception as e:
        logging.error(f"Payment navigation failed: {e}")
        return False

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
                                logging.info("Script paused at Paytm UPI payment page")
                                print("\n" + "="*50)
                                print("PAYMENT PAGE REACHED")
                                print("Proceed manually in the browser")
                                print("Close the browser window when done")
                                print("="*50 + "\n")
                                while True:
                                    time.sleep(1)
        
    except Exception as e:
        logging.error(f"Main error: {str(e)[:100]}")
        print("\nScript encountered an error, but browser will remain open")
        print("Close the browser manually when ready\n")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()