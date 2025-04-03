import os
import time
import base64
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Suppress TensorFlow Lite warnings if they appear (e.g., from EasyOCR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Configure logging for structured output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import the solve_captcha function from your captcha_solver.py
from captcha_solver import solve_captcha

def setup_browser(headless=False, window_size="1920,1080"):
    try:
        options = Options()
        options.page_load_strategy = 'none'  # Keep your intentional setting
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0')
        options.add_argument(f'--window-size={window_size}')

        chromedriver_path = r'C:\Windows\chromedriver.exe'
        if not os.path.exists(chromedriver_path):
            raise FileNotFoundError(f"ChromeDriver not found at {chromedriver_path}")

        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        logging.error(f"Setup error: {e}")
        return None

def interact_with_irctc():
    driver = setup_browser(headless=False, window_size="1920,1080")
    if driver is None:
        return

    try:
        # Navigate to the IRCTC URL
        driver.get('https://www.irctc.co.in/nget/train-search')
        logging.info("Initial page loaded; waiting for LOGIN button...")

        wait = WebDriverWait(driver, 30)

        # Wait explicitly for the LOGIN button to be clickable
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText')))
        logging.info("Login button found: %s", login_button.text)
        driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
        time.sleep(0.5)
        ActionChains(driver).move_to_element(login_button).click(login_button).perform()
        logging.info("Login button clicked.")

        # Wait for the login form to load
        login_form = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'irmodal')))
        logging.info("Login form found.")

        # Find and fill username and password fields
        username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='User Name']")))
        password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Password']")))
        logging.info("Username and password fields found.")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("punam7350")
        password_field.send_keys("Theearthian@1")
        logging.info("Username and password entered.")

        # Wait for CAPTCHA to be visible before proceeding
        wait.until(EC.visibility_of_element_located(
            (By.XPATH, "//app-captcha//div[contains(@class, 'captcha_div')]//span[contains(@class, 'ng-star-inserted')]//img[contains(@class, 'captcha-img')]")
        ))
        logging.info("CAPTCHA visible, proceeding with solving...")

        # Retry loop parameters for sign in attempts
        max_attempts = 3
        attempt = 0
        login_successful = False
        captcha_filename = "captcha.jpg"

        while attempt < max_attempts and not login_successful:
            attempt += 1
            logging.info(f"Sign in attempt {attempt} of {max_attempts}")

            # Locate the CAPTCHA image element (re-read each time)
            try:
                # Use robust XPath for CAPTCHA within app-captcha, captcha_div, and ng-star-inserted span
                captcha_img = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//app-captcha//div[contains(@class, 'captcha_div')]//span[contains(@class, 'ng-star-inserted')]//img[contains(@class, 'captcha-img')]")
                ))
                old_captcha_src = captcha_img.get_attribute("src")
                logging.info("CAPTCHA image element found.")
            except (TimeoutException, NoSuchElementException) as e:
                logging.error("Error locating CAPTCHA image: %s", e)
                # Fallback: Try a broader locator or wait longer
                time.sleep(2)  # Additional delay for dynamic loading
                try:
                    captcha_img = wait.until(EC.presence_of_element_located(
                        (By.XPATH, "//div[contains(@class, 'irmodal')]//img[contains(@class, 'captcha-img')]")
                    ))
                    old_captcha_src = captcha_img.get_attribute("src")
                    logging.info("CAPTCHA found with broader locator.")
                except Exception as e2:
                    logging.error("Could not locate CAPTCHA even with fallback: %s", e2)
                    captcha_text = input("Manual CAPTCHA input (press Enter if none): ").strip()
                    if not captcha_text:
                        logging.warning("No manual input provided, skipping CAPTCHA.")
                        break

            # Save the CAPTCHA image from its base64 source, with error handling
            try:
                if old_captcha_src.startswith("data:image"):
                    base64_data = old_captcha_src.split(",")[1]
                    with open(captcha_filename, "wb") as f:
                        f.write(base64.b64decode(base64_data))
                    logging.info(f"CAPTCHA image saved as '{captcha_filename}'.")
                else:
                    logging.error("Captcha source is not in expected base64 format.")
                    break
            except Exception as e:
                logging.error("Failed to save CAPTCHA image: %s", e)
                break

            # Use Tesseract-based OCR to solve the CAPTCHA, with fallback
            try:
                captcha_text = solve_captcha(captcha_filename)
                logging.info("OCR result: %s", captcha_text)
                if not captcha_text or len(captcha_text) < 4:
                    logging.warning("CAPTCHA text might be invalid or too short: %s", captcha_text)
                    captcha_text = input("Manual CAPTCHA input (press Enter if none): ").strip() or captcha_text
            except Exception as e:
                logging.error("OCR failed, requesting manual input: %s", e)
                captcha_text = input("Manual CAPTCHA input (press Enter if none): ").strip()
                if not captcha_text:
                    logging.warning("No manual input provided, skipping CAPTCHA.")
                    break

            # Locate and fill the CAPTCHA input field, with retry
            try:
                captcha_input = wait.until(EC.presence_of_element_located((By.ID, 'captcha')))
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                logging.info("Entered CAPTCHA text into input field.")
            except (TimeoutException, NoSuchElementException) as e:
                logging.error("Could not find or interact with CAPTCHA input field: %s", e)
                time.sleep(1)  # Retry after a brief pause
                try:
                    captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter Captcha']")))
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)
                    logging.info("Entered CAPTCHA text with fallback locator.")
                except Exception as e2:
                    logging.error("Failed to enter CAPTCHA even with fallback: %s", e2)
                    break

            # Click the Sign In button
            try:
                submit_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class, 'irmodal')]//button[contains(@class, 'train_Search') and contains(., 'SIGN IN')]")
                ))
                ActionChains(driver).move_to_element(submit_button).click(submit_button).perform()
                logging.info("Submit button clicked.")
            except Exception as e:
                logging.error("Could not click Sign In button: %s", e)
                break

            # Wait briefly to see if login is successful (login modal should disappear)
            try:
                wait_short = WebDriverWait(driver, 3)
                login_modal_invisible = wait_short.until(EC.invisibility_of_element_located((By.CLASS_NAME, 'irmodal')))
            except TimeoutException:
                login_modal_invisible = False

            if login_modal_invisible:
                logging.info("Login modal disappeared. Login successful!")
                login_successful = True
                break
            else:
                logging.info("Login modal still visible – likely due to invalid CAPTCHA.")
                # Wait briefly for IRCTC to auto-refresh the CAPTCHA
                time.sleep(2)

        if not login_successful:
            logging.warning("Failed to log in after maximum attempts.")

        # Check for ad iframe and switch if needed (optional, for robustness)
        try:
            ad_iframe = driver.find_element(By.ID, 'div-gpt-ad-36994473-0')
            driver.switch_to.frame(ad_iframe)
            logging.info("Switched to ad iframe.")
            driver.switch_to.default_content()
            logging.info("Returned to default content.")
        except:
            logging.info("No ad iframe found, continuing...")

        # Isolate CAPTCHA and submit button for learning (optional, after login attempt)
        try:
            captcha_img = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//app-captcha//div[contains(@class, 'captcha_div')]//span[contains(@class, 'ng-star-inserted')]//img[contains(@class, 'captcha-img')]")
            ))
            submit_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'irmodal')]//button[contains(@class, 'train_Search') and contains(., 'SIGN IN')]")
            ))
            driver.execute_script("""
                var captcha = arguments[0];
                var submit = arguments[1];
                document.body.innerHTML = '';
                document.body.appendChild(captcha.cloneNode(true));
                document.body.appendChild(submit.cloneNode(true));
                document.body.style.background = 'white';
            """, captcha_img, submit_button)
            driver.save_screenshot('irctc_captcha_desktop.png')
            logging.info("CAPTCHA and submit button isolated. Check 'irctc_captcha_desktop.png'.")
        except Exception as e:
            logging.error("Could not isolate CAPTCHA and submit button: %s", e)

    except Exception as e:
        logging.error("Error: %s", e)
        with open('page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        driver.save_screenshot('error_screenshot.png')
        logging.info("Saved page_source.html and error_screenshot.png for debugging.")

    finally:
        driver.quit()
        logging.info("Browser closed.")

if __name__ == "__main__":
    interact_with_irctc()