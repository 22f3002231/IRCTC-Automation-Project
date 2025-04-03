import os
import time
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# Suppress TensorFlow Lite warnings if they appear (e.g., from EasyOCR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Import the solve_captcha function from your captcha_solver.py
from captcha_solver import solve_captcha

def setup_browser(headless=False, window_size="1920,1080"):
    try:
        options = Options()
        # Set page load strategy to 'none' so the driver doesn't wait for full page load
        options.page_load_strategy = 'none'
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
        print(f"Setup error: {e}")
        return None

def interact_with_irctc():
    driver = setup_browser(headless=False, window_size="1920,1080")
    if driver is None:
        return

    try:
        # Navigate to the IRCTC URL. With page_load_strategy 'none', this returns quickly.
        driver.get('https://www.irctc.co.in/nget/train-search')
        print("Initial page loaded; waiting for LOGIN button...")

        wait = WebDriverWait(driver, 30)

        # Wait explicitly for the LOGIN button to be clickable
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'loginText')))
        print("Login button found:", login_button.text)
        driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
        time.sleep(0.5)
        ActionChains(driver).move_to_element(login_button).click(login_button).perform()
        print("Login button clicked.")

        # Wait for the username and password fields (do not wait for entire modal load)
        username_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='User Name']")))
        password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Password']")))
        print("Username and password fields found.")
        username_field.clear()
        password_field.clear()
        username_field.send_keys("punam7350")
        password_field.send_keys("Theearthian@1")
        print("Username and password entered.")

        # Retry loop parameters for sign in attempts
        max_attempts = 3
        attempt = 0
        login_successful = False
        captcha_filename = "captcha.jpg"

        while attempt < max_attempts and not login_successful:
            attempt += 1
            print(f"\nSign in attempt {attempt} of {max_attempts}")

            # Locate the CAPTCHA image element (re-read each time)
            try:
                captcha_img = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, 'irmodal')]//div[contains(@class, 'captcha_div')]//img[contains(@class, 'captcha-img')]")
                ))
                old_captcha_src = captcha_img.get_attribute("src")
                print("CAPTCHA image element found.")
            except Exception as e:
                print("Error locating CAPTCHA image:", e)
                break

            # Save the CAPTCHA image from its base64 source
            if old_captcha_src.startswith("data:image"):
                base64_data = old_captcha_src.split(",")[1]
                with open(captcha_filename, "wb") as f:
                    f.write(base64.b64decode(base64_data))
                print(f"CAPTCHA image saved as '{captcha_filename}'.")
            else:
                print("Captcha source is not in expected base64 format.")
                break

            # Use Tesseract-based OCR to solve the CAPTCHA
            captcha_text = solve_captcha(captcha_filename)
            print("OCR result:", captcha_text)

            # Re-locate and clear the CAPTCHA input field
            try:
                captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter Captcha']")))
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                print("Entered CAPTCHA text into input field.")
            except Exception as e:
                print("Could not find or interact with CAPTCHA input field:", e)
                break

            # Click the Sign In button
            try:
                submit_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[contains(@class, 'irmodal')]//button[contains(@class, 'train_Search') and contains(., 'SIGN IN')]")
                ))
                ActionChains(driver).move_to_element(submit_button).click(submit_button).perform()
                print("Submit button clicked.")
            except Exception as e:
                print("Could not click Sign In button:", e)
                break

            # Wait briefly to see if login is successful (login modal should disappear)
            try:
                wait_short = WebDriverWait(driver, 3)
                login_modal_invisible = wait_short.until(EC.invisibility_of_element_located((By.CLASS_NAME, 'irmodal')))
            except TimeoutException:
                login_modal_invisible = False

            if login_modal_invisible:
                print("Login modal disappeared. Login successful!")
                login_successful = True
                break
            else:
                print("Login modal still visible – likely due to invalid CAPTCHA.")
                # Wait briefly for IRCTC to auto-refresh the CAPTCHA
                time.sleep(1)

        if not login_successful:
            print("Failed to log in after maximum attempts.")

    except Exception as e:
        print("Error:", e)
        with open('page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        driver.save_screenshot('error_screenshot.png')
        print("Saved page_source.html and error_screenshot.png for debugging.")

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    interact_with_irctc()
