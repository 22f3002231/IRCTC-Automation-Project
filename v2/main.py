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
from datetime import datetime

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
JOURNEY_CLASS = ""  # Leave blank for now (we'll set it later)
JOURNEY_QUOTA = "GENERAL"   # We'll send its first letter ("t")

# Prefilled train and class for automation (no user prompt)
JOURNEY_TRAIN = "12859"  # Example: LTT GAYA SF EXP
JOURNEY_CLASS = "SL"     # Example: AC 3 Tier
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

def login_irctc(driver, wait):
    try:
        # Click the login button (only once)
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText'))).click()
        
        # Fill in username and password via JavaScript injection.
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
            # Click SIGN IN using a clickable wait
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'SIGN IN')]"))).click()
            time.sleep(0.5)  # Reduced sleep to check login feedback sooner

            try:
                # Use a shorter timeout for login feedback
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
                    time.sleep(0.5)  # Short pause before next attempt
            except TimeoutException:
                logging.info("Timeout waiting for login feedback; retrying captcha...")
        return False
    except (NoSuchElementException, TimeoutException, ElementNotInteractableException) as e:
        logging.error(f"Login error: {e}")
        return False

















def fill_train_search(driver):
    try:
        # Use JavaScript injection to fill origin, destination, and journey date
        data = {
            "p-autocomplete[formcontrolname='origin'] input": FROM_STATION,
            "p-autocomplete[formcontrolname='destination'] input": TO_STATION,
            "p-calendar[formcontrolname='journeyDate'] input": JOURNEY_DATE,
        }
        js_script = """
        var data = arguments[0];
        for (var selector in data) {
            var el = document.querySelector(selector);
            if (el) {
                el.value = data[selector];
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
        """
        driver.execute_script(js_script, data)

        # Optimized journey quota setting
        quota_initial = JOURNEY_QUOTA[0].lower()  # e.g., "t" for "TATKAL"
        quota_js = """
        var quotaDropdown = document.querySelector("p-dropdown[formcontrolname='journeyQuota']");
        var input = quotaDropdown.querySelector('input');
        var label = quotaDropdown.querySelector('.ui-dropdown-label');
        var quotas = {'t': 'TATKAL', 'g': 'GENERAL', 'l': 'LADIES'};
        var selectedQuota = quotas[arguments[0]] || 'GENERAL';
        if (input) {
            input.value = selectedQuota;
            input.setAttribute('aria-label', selectedQuota);
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (label) label.textContent = selectedQuota;
        return selectedQuota;
        """
        selected_quota = driver.execute_script(quota_js, quota_initial)
        logging.info(f"Set journey quota to: {selected_quota}")

        # Use WebDriverWait for the Search button
        wait = WebDriverWait(driver, TIMEOUT)
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Search')]")))
        search_button.click()
        logging.info("Train search submitted successfully!")

        # Wait for the train list page to load (URL changes and train elements appear)
        wait.until(EC.url_contains("/nget/booking/train-list"))
        wait.until(EC.presence_of_element_located((By.XPATH, "//app-train-avl-enq")))

        logging.info("Navigated to train list page successfully!")
    except Exception as e:
        logging.error(f"Train search error: {e}")


















def list_trains(driver):
    try:
        # Use WebDriverWait to ensure train list elements are present
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.XPATH, "//app-train-avl-enq")))

        # Find all train containers
        trains = driver.find_elements(By.XPATH, "//app-train-avl-enq")
        logging.info(f"Found {len(trains)} trains on the list.")

        # Store train details
        train_details = []
        for train in trains:
            # Extract train number (e.g., "22357" from "LTT GAYA SF EXP (22357)")
            train_number = train.find_element(By.XPATH, ".//strong[contains(., '(')]").text.split("(")[1].split(")")[0]
            # Extract train name (e.g., "LTT GAYA SF EXP")
            train_name = train.find_element(By.XPATH, ".//strong[contains(., '(')]").text.split("(")[0].strip()
            # Extract available classes (e.g., "SL", "3E", "3A", "2A", "1A") from <div class="pre-avl">
            classes = train.find_elements(By.XPATH, ".//div[contains(@class, 'pre-avl')]//strong")
            class_names = [cls.text.split("(")[1].split(")")[0] for cls in classes if "(" in cls.text]

            train_info = {
                "number": train_number,
                "name": train_name,
                "classes": class_names
            }
            train_details.append(train_info)
            logging.info(f"Train: {train_name} ({train_number}), Classes: {class_names}")

        return train_details  # Return for later use (e.g., prefill)
    except Exception as e:
        logging.error(f"Error listing trains: {e}")
        return []











def select_train_and_class(driver, train_details):
    try:
        # Find the train with the specified train number from train_details
        target_train = next((train for train in train_details if train["number"] == JOURNEY_TRAIN), None)
        if not target_train:
            logging.error(f"Train {JOURNEY_TRAIN} not found in the list.")
            return False

        logging.info(f"Selecting train: {target_train['name']} ({target_train['number']})")

        # Locate the train's <app-train-avl-enq> div using the train number
        # Use a more robust XPath to ensure we find the correct train container
        train_element = driver.find_element(By.XPATH, f"//app-train-avl-enq//strong[contains(., '({JOURNEY_TRAIN})')]/../../../../..")
        
        # Wait for the class table to be present and clickable
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(EC.presence_of_element_located((By.XPATH, ".//div[contains(@class, 'white-back')]//table")))
        
        # Find all class divs for this train within the <table> inside <div class="white-back">
        # Use a precise XPath to target <div class="pre-avl"> within <table> and <td>
        class_divs = train_element.find_elements(By.XPATH, ".//div[contains(@class, 'white-back')]//table//td//div[contains(@class, 'pre-avl')]")
        target_class_found = False

        for class_div in class_divs:
            # Ensure the div is clickable before interacting
            wait.until(EC.element_to_be_clickable(class_div))
            
            # Get the full text from the <strong> tag inside the <div class="pre-avl">
            try:
                class_text = class_div.find_element(By.XPATH, ".//strong").text.strip()
            except NoSuchElementException:
                logging.debug(f"No <strong> found in div: {class_div.get_attribute('outerHTML')}")
                continue
            
            logging.debug(f"Checking class: {class_text}")  # Debug log to trace what’s found
            
            # Extract the class code (e.g., "3A" from "AC 3 Tier (3A)")
            if "(" in class_text and ")" in class_text:
                class_name = class_text.split("(")[1].split(")")[0]
            else:
                continue  # Skip if the format doesn’t match our expectation

            if class_name == JOURNEY_CLASS:
                # Click the <div class="pre-avl"> to load seat availability
                class_div.click()  # Click the entire <div class="pre-avl">
                # Wait for seat availability to load (e.g., WL, RAC, or REGRET classes)
                wait.until(EC.presence_of_element_located((By.XPATH, ".//div[contains(@class, 'pre-avl')]//div[contains(@class, 'WL') or contains(@class, 'RAC') or contains(@class, 'REGRET')]")))
                logging.info(f"Selected class: {class_name} for train {JOURNEY_TRAIN}")
                target_class_found = True
                break

        if not target_class_found:
            logging.error(f"Class {JOURNEY_CLASS} not found for train {JOURNEY_TRAIN}")
            return False

        return True
    except Exception as e:
        logging.error(f"Error selecting train and class: {e}")
        return False








def check_seat_availability_and_readiness(driver):
    try:
        # Wait for the seat availability table to load after class selection
        wait = WebDriverWait(driver, TIMEOUT)
        availability_table = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//div[contains(@style, 'overflow-x: auto; width: 100%;')]//table")
        ))

        # Convert JOURNEY_DATE to match the HTML format (e.g., "Wed, 25 Feb")
        # Assuming JOURNEY_DATE is in "DD/MM/YYYY" format (e.g., "25/02/2025")
        date_obj = datetime.strptime(JOURNEY_DATE, "%d/%m/%Y")
        formatted_date = date_obj.strftime("%a, %d %b").lower()  # e.g., "wed, 25 feb"

        # Find the date div matching the prefilled JOURNEY_DATE
        date_divs = availability_table.find_elements(By.XPATH, ".//div[contains(@class, 'pre-avl')]")
        target_date_div = None

        for date_div in date_divs:
            date_text = date_div.find_element(By.XPATH, ".//strong").text.strip().lower()  # e.g., "wed, 16 apr"
            if formatted_date in date_text:
                target_date_div = date_div
                break

        if not target_date_div:
            logging.error(f"Date {JOURNEY_DATE} not found in the availability table.")
            return None, False

        # Click the matching date div to select it
        target_date_div.click()
        logging.info(f"Selected date: {target_date_div.find_element(By.XPATH, './/strong').text.strip()}")

        # Wait for the page to update after date selection (ensure availability refreshes)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, ".//div[contains(@class, 'pre-avl') and contains(@class, 'selected-class')]//strong")
        ))

        # Check the updated availability for the selected date
        selected_availability_div = wait.until(EC.presence_of_element_located(
            (By.XPATH, ".//div[contains(@class, 'pre-avl') and contains(@class, 'selected-class')]//div[contains(@class, 'WL') or contains(@class, 'AVAILABLE')]//strong")
        ))
        selected_availability = selected_availability_div.text.strip()
        logging.info(f"Seat availability for selected date {JOURNEY_DATE}: {selected_availability}")

        # Check if booking is ready (no '#' in availability and "Book Now" button enabled)
        booking_ready = "#" not in selected_availability
        if booking_ready:
            # Poll for the "Book Now" button to become enabled
            script = "return document.querySelector('.btnDefault.train_Search').disabled;"
            while driver.execute_script(script):
                time.sleep(0.1)  # Quick poll every 0.1 seconds
            logging.info("Booking button is now enabled!")

            # Verify the button is clickable (no longer has 'disable-book' class)
            book_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btnDefault train_Search')]")))
            button_class = book_button.get_attribute("class")
            if "disable-book" not in button_class:
                logging.info("Train is ready to book for the selected date!")
                return selected_availability, True  # Return availability and readiness
            else:
                logging.warning("Train is not ready to book yet.")
                return selected_availability, False
        else:
            logging.warning("Booking not started yet (availability ends with '#').")
            return selected_availability, False

    except Exception as e:
        logging.error(f"Error checking seat availability and readiness: {e}")
        return None, False






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
                # List trains after search
                train_details = list_trains(driver)
                logging.info(f"Train details collected: {train_details}")
                # Select the prefilled train and class
                if select_train_and_class(driver, train_details):
                    logging.info("Successfully selected train and class.")
                    # Check seat availability and booking readiness for the prefilled date
                    seat_availability, is_ready = check_seat_availability_and_readiness(driver)
                    if seat_availability and is_ready:
                        logging.info("Proceeding with booking preparations...")
                    else:
                        logging.warning("Cannot proceed with booking due to unavailable seats or booking not started.")
                else:
                    logging.warning("Failed to select train and class.")
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
