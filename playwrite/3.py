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
JOURNEY_DATE = "20/04/2025"
JOURNEY_QUOTA = "SLEEPER"

# NEW GLOBALS needed for train selection
JOURNEY_TRAIN = "12859"   # change as per your journey details
JOURNEY_CLASS = "SL"      # e.g., "SL" for Sleeper

def setup_browser():
    """Initialize Playwright browser with performance optimizations."""
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
    """Perform login with manual CAPTCHA handling."""
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
    """Fill the train search form with robust date handling."""
    try:
        logging.info("Starting train search form filling...")

        # From Station
        from_input = "p-autocomplete[formcontrolname='origin'] input"
        page.wait_for_selector(from_input, state="visible", timeout=TIMEOUT*1000)
        page.fill(from_input, FROM_STATION)
        page.eval_on_selector(from_input, "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")
        logging.info(f"From station set: {FROM_STATION}")

        # To Station
        to_input = "p-autocomplete[formcontrolname='destination'] input"
        page.fill(to_input, TO_STATION)
        page.eval_on_selector(to_input, "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")
        logging.info(f"To station set: {TO_STATION}")

        # Date - Using keyboard simulation
        date_input = "p-calendar[formcontrolname='journeyDate'] input"
        page.wait_for_selector(date_input, state="visible", timeout=TIMEOUT*1000)
        page.click(date_input)
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        page.type(date_input, JOURNEY_DATE)
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        
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
        page.screenshot(path="form_error.png")

# --- New Functions converted from Selenium ---

def list_trains(page):
    """List trains from the search results using Playwright by waiting for a visible descendant."""
    try:
        # Wait for the strong element inside the train heading to be visible.
        page.wait_for_selector("xpath=//app-train-avl-enq//div[contains(@class, 'train-heading')]/strong", 
                                 timeout=1000)
        # Now get all train containers.
        trains = page.query_selector_all("xpath=//app-train-avl-enq")
        logging.info(f"Found {len(trains)} train containers on the list.")
        train_details = []
        for train in trains:
            try:
                # Extract the train heading (e.g. "HOWRAH DURONTO (12261)")
                heading = train.query_selector("xpath=.//div[contains(@class, 'train-heading')]/strong")
                if not heading:
                    continue
                text = heading.inner_text().strip()
                if "(" in text and ")" in text:
                    train_name = text.split("(")[0].strip()
                    train_number = text.split("(")[1].split(")")[0].strip()
                else:
                    continue

                # Extract available classes from each train container.
                class_elements = train.query_selector_all("xpath=.//div[contains(@class, 'pre-avl')]//strong")
                class_names = []
                for cls in class_elements:
                    cls_text = cls.inner_text().strip()
                    if "(" in cls_text and ")" in cls_text:
                        cls_code = cls_text.split("(")[1].split(")")[0].strip()
                        class_names.append(cls_code)
                    else:
                        class_names.append(cls_text)
                
                train_info = {
                    "number": train_number,
                    "name": train_name,
                    "classes": class_names
                }
                train_details.append(train_info)
                logging.info(f"Train: {train_name} ({train_number}), Classes: {class_names}")
            except Exception as inner_e:
                logging.debug(f"Error processing a train element: {inner_e}")
        return train_details
    except Exception as e:
        logging.error(f"Error listing trains: {e}")
        return []


def select_train_and_class(page, train_details):
    """Select a specific train and class from the search results using Playwright."""
    try:
        # Find the train with the specified train number
        target_train = next((train for train in train_details if train["number"] == JOURNEY_TRAIN), None)
        if not target_train:
            logging.error(f"Train {JOURNEY_TRAIN} not found in the list.")
            return False

        logging.info(f"Selecting train: {target_train['name']} ({target_train['number']})")
        # Locate the train container using a robust XPath
        train_selector = f"xpath=//app-train-avl-enq//strong[contains(., '({JOURNEY_TRAIN})')]/../../../../.."
        train_element = page.wait_for_selector(train_selector, timeout=TIMEOUT*1000)

        # Wait for the class table within the train element
        train_element.wait_for_selector("xpath=.//div[contains(@class, 'white-back')]//table", timeout=TIMEOUT*1000)
        # Get all class divs
        class_divs = train_element.query_selector_all("xpath=.//div[contains(@class, 'white-back')]//table//td//div[contains(@class, 'pre-avl')]")
        target_class_found = False

        for class_div in class_divs:
            try:
                class_text = class_div.query_selector("xpath=.//strong").inner_text().strip()
            except Exception:
                logging.debug(f"No <strong> found in div: {class_div.inner_html()}")
                continue

            logging.debug(f"Checking class: {class_text}")
            if "(" in class_text and ")" in class_text:
                class_code = class_text.split("(")[1].split(")")[0].strip()
            else:
                continue

            if class_code == JOURNEY_CLASS:
                class_div.click()
                # Wait for seat availability to load (look for WL, RAC, or REGRET indicators)
                page.wait_for_selector("xpath=.//div[contains(@class, 'pre-avl')]//div[contains(@class, 'WL') or contains(@class, 'RAC') or contains(@class, 'REGRET')]", timeout=TIMEOUT*1000)
                logging.info(f"Selected class: {class_code} for train {JOURNEY_TRAIN}")
                target_class_found = True
                break

        if not target_class_found:
            logging.error(f"Class {JOURNEY_CLASS} not found for train {JOURNEY_TRAIN}")
            return False

        return True
    except Exception as e:
        logging.error(f"Error selecting train and class: {e}")
        return False

def check_seat_availability_and_readiness(page):
    """Check seat availability and booking readiness using Playwright."""
    try:
        # Wait for the seat availability table to load
        availability_table = page.wait_for_selector("xpath=//div[contains(@style, 'overflow-x: auto; width: 100%;')]//table", timeout=TIMEOUT*1000)
        
        # Convert JOURNEY_DATE (dd/mm/yyyy) to match HTML format (e.g., "wed, 25 feb")
        date_obj = datetime.strptime(JOURNEY_DATE, "%d/%m/%Y")
        formatted_date = date_obj.strftime("%a, %d %b").lower()

        # Find the date div that matches the formatted date
        date_divs = availability_table.query_selector_all("xpath=.//div[contains(@class, 'pre-avl')]")
        target_date_div = None
        for date_div in date_divs:
            try:
                date_text = date_div.query_selector("xpath=.//strong").inner_text().strip().lower()
            except Exception:
                continue
            if formatted_date in date_text:
                target_date_div = date_div
                break

        if not target_date_div:
            logging.error(f"Date {JOURNEY_DATE} not found in the availability table.")
            return None, False

        # Click the matching date div to select it
        target_date_div.click()
        logging.info(f"Selected date: {target_date_div.query_selector('xpath=.//strong').inner_text().strip()}")

        # Wait for page update after date selection
        page.wait_for_selector("xpath=.//div[contains(@class, 'pre-avl') and contains(@class, 'selected-class')]//strong", timeout=TIMEOUT*1000)
        # Wait for the updated availability element to appear
        availability_selector = "xpath=.//div[contains(@class, 'pre-avl') and contains(@class, 'selected-class')]//div[contains(@class, 'WL') or contains(@class, 'AVAILABLE')]//strong"
        selected_availability_elem = page.wait_for_selector(availability_selector, timeout=TIMEOUT*1000)
        selected_availability = selected_availability_elem.inner_text().strip()
        logging.info(f"Seat availability for selected date {JOURNEY_DATE}: {selected_availability}")

        # Determine if booking is ready (availability should not contain '#')
        booking_ready = "#" not in selected_availability
        if booking_ready:
            # Poll for the "Book Now" button to become enabled using wait_for_function
            page.wait_for_function(
                "() => { const btn = document.querySelector('.btnDefault.train_Search'); return btn && !btn.disabled; }",
                timeout=60000
            )
            # Additionally, ensure the button does not have the 'disable-book' class
            book_button = page.wait_for_selector("xpath=//button[contains(@class, 'btnDefault train_Search') and not(contains(@class, 'disable-book'))]", timeout=TIMEOUT*1000)
            if book_button:
                logging.info("Train is ready to book for the selected date!")
                return selected_availability, True
            else:
                logging.warning("Train is not ready to book yet.")
                return selected_availability, False
        else:
            logging.warning("Booking not started yet (availability contains '#').")
            return selected_availability, False

    except Exception as e:
        logging.error(f"Error checking seat availability and readiness: {e}")
        return None, False

# --- Main flow demonstrating the new functionality ---

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
            # Wait for search results to load before proceeding (adjust sleep as needed)
            page.wait_for_timeout(5000)
            
            # List available trains
            trains = list_trains(page)
            if not trains:
                logging.error("No trains found.")
                return
            
            # Select the desired train and class
            if not select_train_and_class(page, trains):
                logging.error("Failed to select train and class.")
                return

            # Check seat availability and whether booking is ready
            availability, ready = check_seat_availability_and_readiness(page)
            if availability is not None:
                logging.info(f"Availability: {availability}, Booking Ready: {ready}")
            else:
                logging.error("Failed to get seat availability.")

            # Continue with further booking steps (e.g., passenger input) as needed.
            time.sleep(5)
        
    except Exception as e:
        logging.error(f"Main error: {e}")
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    main()
