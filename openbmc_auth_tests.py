import unittest
import time
from seleniumwire import webdriver # Changed from selenium to seleniumwire
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import HtmlTestRunner
import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
OPENBMC_HOST = "https://localhost:2443"
USERNAME = "root"
PASSWORD = "0penBmc" # Default OpenBMC password
INVALID_PASSWORD = "invalidpassword"
REPORTS_DIR = 'reports'

class OpenBMCAuthTests(unittest.TestCase):
    driver = None

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up OpenBMCAuthTests class...")
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-certificate-errors") # Browser ignores cert errors from server
        chrome_options.add_argument("--disable-gpu") # Often recommended for headless

        # Selenium-wire specific options
        # This tells selenium-wire's proxy to ignore SSL errors from the OpenBMC server (self-signed certs)
        sw_options = {
            'verify_ssl': False
        }
        
        # Use seleniumwire.webdriver
        cls.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)
        cls.base_url = OPENBMC_HOST
        logger.info("WebDriver (selenium-wire) initialized.")

    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down OpenBMCAuthTests class...")
        if cls.driver:
            cls.driver.quit()
            logger.info("WebDriver quit.")

    def setUp(self):
        logger.info(f"\n--- Test: {self._testMethodName} ---")
        # Clear requests from a previous test run, if any existed
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Clearing {len(self.driver.requests)} requests from previous test.")
            del self.driver.requests
        
        logger.info(f"Navigating to base URL: {self.base_url}")
        self.driver.get(self.base_url)
        time.sleep(3) 
        
        if hasattr(self.driver, 'requests'):
            logger.info(f"Captured {len(self.driver.requests)} requests after navigating to base_url ({self.base_url}):")
            if not self.driver.requests:
                logger.info("  No requests captured by selenium-wire for initial page load.")
            for i, req in enumerate(self.driver.requests):
                status_code = req.response.status_code if req.response else 'No resp'
                logger.info(f"  Initial Nav Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {status_code}")
        else:
            logger.warning("  self.driver does not have 'requests' attribute after initial get(). Selenium-wire might not be active.")

        logger.info("Clearing requests before performing login action...")
        if hasattr(self.driver, 'requests'):
            del self.driver.requests


    def tearDown(self):
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Clearing {len(self.driver.requests)} requests at end of {self._testMethodName}.")
            del self.driver.requests
        logger.info(f"--- End Test: {self._testMethodName} ---")


    def _perform_login(self, username, password):
        try:
            username_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            login_buttons = self.driver.find_elements(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')] | //button[@type='submit'] | //input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]")
            if not login_buttons:
                self.fail("Login button not found.")
            login_button = login_buttons[0]

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            logger.info("Clearing requests immediately before clicking login button...")
            if hasattr(self.driver, 'requests'):
                del self.driver.requests 
            
            logger.info("Clicking login button...")
            login_button.click()
            
            logger.info("Waiting for login action's network request to be captured (up to 10s)...")
            WebDriverWait(self.driver, 10).until(
                lambda wd: hasattr(wd, 'requests') and len(wd.requests) > 0
            )

        except TimeoutException:
            page_source_snippet = self.driver.page_source[:500]
            self.fail(f"Login form elements not found or login action did not generate network requests within timeout on page {self.driver.current_url}. Title: '{self.driver.title}'. Source snippet: {page_source_snippet}")
        except NoSuchElementException:
            self.fail(f"Login form elements (username, password, or button) not found by fallback on page {self.driver.current_url}. Current page title: '{self.driver.title}'.")


    def test_successful_login(self):
        logger.info(f"Attempting successful login with user: {USERNAME}")
        self._perform_login(USERNAME, PASSWORD)
        
        self.assertTrue(hasattr(self.driver, 'requests'), "self.driver has no 'requests' attribute. Selenium-wire problem.")
        self.assertTrue(len(self.driver.requests) > 0, "No requests captured after login attempt.")

        logger.info(f"Captured {len(self.driver.requests)} requests during/after successful login attempt:")
        
        login_post_request = None
        for i, req in enumerate(self.driver.requests):
            status_code = req.response.status_code if req.response else "No response"
            logger.info(f"  Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {status_code}")
            if req.response and req.response.body:
                try:
                    body_snippet = req.response.body.decode('utf-8', errors='ignore')[:100]
                    logger.info(f"    Response Body Snippet: {body_snippet}...")
                except Exception as e:
                    logger.info(f"    Error decoding/printing response body: {e}")

            # More specific check for OpenBMC login POST
            if req.method == 'POST' and "SessionService/Sessions" in req.url:
                login_post_request = req
                logger.info(f"  *** Identified OpenBMC login POST request: {req.url} ***")
                break
        
        self.assertIsNotNone(login_post_request, "No OpenBMC login POST request captured ('SessionService/Sessions'). Check printed requests.")
        
        self.assertIn(login_post_request.response.status_code, [200, 201],
                      f"Expected successful login status code (200 or 201) on POST {login_post_request.url}, "
                      f"got {login_post_request.response.status_code}. "
                      f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")

        logger.info(f"Successful login POST to {login_post_request.url} confirmed with status {login_post_request.response.status_code}.")

        try:
            WebDriverWait(self.driver, 10).until(lambda d: "dashboard" in d.current_url.lower() or d.execute_script("return document.readyState === 'complete'"))
            logger.info(f"Login appears successful. Current URL: {self.driver.current_url}")
        except TimeoutException:
            self.fail(f"Login network call successful, but did not redirect to a 'dashboard' URL or page did not fully load. Current URL: {self.driver.current_url}")


    def test_invalid_credentials(self):
        logger.info(f"Attempting invalid login with user: {USERNAME}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        self.assertTrue(hasattr(self.driver, 'requests'), "self.driver has no 'requests' attribute. Selenium-wire problem.")
        
        login_post_request = None
        logger.info(f"Captured {len(self.driver.requests)} requests during/after invalid login attempt:")
        if not self.driver.requests:
            logger.info("  No requests were captured by selenium-wire at all after invalid login click.")

        for i, req in enumerate(self.driver.requests):
            status_code = req.response.status_code if req.response else 'No response'
            logger.info(f"  Request #{i+1} (invalid login): URL: {req.url}, Method: {req.method}, Status: {status_code}")
            if req.method == 'POST' and "SessionService/Sessions" in req.url:
                login_post_request = req
                logger.info(f"  *** Identified OpenBMC invalid login POST request: {req.url} ***")
                break
        
        if login_post_request and login_post_request.response:
            self.assertIn(login_post_request.response.status_code, [400, 401, 403],
                          f"Expected error status code (400/401/403) for invalid login POST to {login_post_request.url}, "
                          f"got {login_post_request.response.status_code}. "
                          f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")
            logger.info(f"Invalid login POST to {login_post_request.url} correctly received error status {login_post_request.response.status_code}.")
        else:
            logger.info("No specific login POST request found for invalid login, or no error response via network. Checking UI for error message.")
            try:
                error_message_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'invalid credentials') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login failed') or contains(@class, 'error') or contains(@role, 'alert') or contains(text(),'Unauthorized')]"))
                )
                self.assertTrue(error_message_element.is_displayed(), "Error message element found but not displayed")
                logger.info(f"Found UI error message for invalid login: {error_message_element.text}")
            except TimeoutException:
                self.fail("Failed to find an error message on the UI after invalid login attempt, AND no conclusive network error was found/identified.")


if __name__ == '__main__':
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    
    unittest.main(verbosity=2, testRunner=HtmlTestRunner.HTMLTestRunner(output=REPORTS_DIR, report_name="selenium_webui_report", add_timestamp=False))
