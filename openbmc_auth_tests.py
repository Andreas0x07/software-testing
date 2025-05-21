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

# Configure basic logging for test visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
OPENBMC_HOST = "https://localhost:2443"
USERNAME = "root"
PASSWORD = "0penBmc" # Default OpenBMC password
INVALID_PASSWORD = "invalidpassword"

class OpenBMCAuthTests(unittest.TestCase):
    driver = None
    base_url = OPENBMC_HOST

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up OpenBMCAuthTests class...")
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--ignore-certificate-errors") # Browser ignores cert errors from server

        # Selenium-wire options
        # Instructs selenium-wire's proxy to ignore SSL errors from the upstream server (OpenBMC)
        sw_options = {
            'verify_ssl': False,
            'connection_timeout': 60 # Optional: increase connection timeout
        }
        
        # Use seleniumwire.webdriver.Chrome
        cls.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)
        logger.info("WebDriver (Selenium Wire) initialized.")

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
            logger.info(f"Clearing {len(self.driver.requests)} requests from previous test run.")
            del self.driver.requests
        
        logger.info(f"Navigating to base URL: {self.base_url}")
        self.driver.get(self.base_url)
        # Allow time for page to load and selenium-wire to capture initial request(s)
        time.sleep(5) # Increased slightly for potentially slower CI environments
        
        if hasattr(self.driver, 'requests'):
            logger.info(f"Captured {len(self.driver.requests)} requests after navigating to base_url ({self.base_url}):")
            if not self.driver.requests:
                logger.info("  No requests captured by selenium-wire for initial page load.")
            for i, req in enumerate(self.driver.requests):
                status_code = req.response.status_code if req.response else 'No response'
                logger.info(f"  Initial Nav Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {status_code}")
        else:
            # This should not happen if using selenium-wire's webdriver
            logger.error("  self.driver does not have 'requests' attribute. Selenium-wire might not be active.")

        logger.info("Clearing requests captured during page load before performing login action...")
        if hasattr(self.driver, 'requests'):
            del self.driver.requests
        else:
            logger.warning("No 'requests' attribute to clear; this is unexpected if selenium-wire is active.")


    def tearDown(self):
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Clearing {len(self.driver.requests)} requests at end of {self._testMethodName}.")
            del self.driver.requests
        logger.info(f"--- End Test: {self._testMethodName} ---")


    def _perform_login(self, username, password):
        try:
            username_field = WebDriverWait(self.driver, 20).until( # Increased wait time
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            # Making the XPath for login button more robust
            login_button_xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')] | //button[@type='submit'] | //input[@type='submit' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]"
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            logger.info("Clearing requests immediately before clicking login button...")
            if hasattr(self.driver, 'requests'):
                del self.driver.requests 
            
            logger.info("Clicking login button...")
            login_button.click()
            
            logger.info("Waiting for login action's network request to be captured (5s)...")
            time.sleep(5)

        except TimeoutException:
            page_source_snippet = self.driver.page_source[:1000] if self.driver.page_source else "N/A"
            self.fail(f"Login form elements (username, password, or button) not found or not clickable on page {self.driver.current_url}. Current page title: '{self.driver.title}'. Page source snippet: {page_source_snippet}")
        except NoSuchElementException: # Should be caught by WebDriverWait generally
            self.fail(f"Login form elements (username, password, or button) not found by fallback on page {self.driver.current_url}. Current page title: '{self.driver.title}'.")


    def test_successful_login(self):
        """Login with valid credentials and check for successful HTTP response."""
        logger.info(f"Attempting successful login with user: {USERNAME}")
        self._perform_login(USERNAME, PASSWORD)
        
        if not hasattr(self.driver, 'requests'):
            self.fail("self.driver has no 'requests' attribute after login attempt. Selenium-wire problem or not initialized correctly.")

        logger.info(f"Captured {len(self.driver.requests)} requests during/after successful login attempt:")
        if not self.driver.requests:
            logger.warning("  No requests were captured by selenium-wire after login click. This might indicate the click didn't trigger a network request or an issue with selenium-wire.")
        
        login_post_request = None
        for i, req in enumerate(self.driver.requests):
            status_code = req.response.status_code if req.response else 'No response'
            logger.info(f"  Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {status_code}")
            if req.response and req.response.body:
                try:
                    body_snippet = req.response.body.decode('utf-8', errors='ignore')[:200]
                    logger.info(f"    Response Body Snippet: {body_snippet}")
                except Exception as e:
                    logger.info(f"    Error decoding/printing response body: {e}")

            # Adjusted condition to be more specific for OpenBMC Redfish session
            if req.method == 'POST' and '/redfish/v1/SessionService/Sessions' in req.url:
                login_post_request = req
                logger.info(f"  *** Identified potential login POST request: {req.url} ***")
                break 
        
        self.assertIsNotNone(login_post_request, "No suitable login POST request captured. Check network logs and URL filters.")
        self.assertIsNotNone(login_post_request.response, f"Login POST request to {login_post_request.url} was captured but has no response object.")
        
        self.assertIn(login_post_request.response.status_code, [200, 201], 
                      f"Expected successful login status code (200 or 201) on POST {login_post_request.url}, "
                      f"got {login_post_request.response.status_code}. "
                      f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500] if login_post_request.response.body else 'N/A'}")

        logger.info(f"Successful login POST to {login_post_request.url} confirmed with status {login_post_request.response.status_code}.")

        try:
            # OpenBMC might not redirect to 'dashboard', it might stay on the same page or update it.
            # A more reliable check after login might be to look for a logout button or user-specific element.
            # For now, we'll check if the URL is still the base_url or a variant.
            WebDriverWait(self.driver, 10).until(
                lambda driver: "session" not in driver.current_url.lower() and "login" not in driver.current_url.lower()
            )
            logger.info(f"Login appears successful. Current URL: {self.driver.current_url}")
        except TimeoutException:
            logger.warning(f"Login network call successful, but URL did not change as expected or still indicates login/session page. Current URL: {self.driver.current_url}. This might be acceptable depending on application behavior.")


    def test_invalid_credentials(self):
        """Attempt login with invalid credentials and check for failure indication."""
        logger.info(f"Attempting invalid login with user: {USERNAME}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        if not hasattr(self.driver, 'requests'):
            self.fail("self.driver has no 'requests' attribute after invalid login attempt. Selenium-wire problem.")

        login_post_request = None
        logger.info(f"Captured {len(self.driver.requests)} requests during/after invalid login attempt:")
        if not self.driver.requests:
            logger.warning("  No requests were captured by selenium-wire after invalid login click.")

        for i, req in enumerate(self.driver.requests):
            status_code = req.response.status_code if req.response else 'No response'
            logger.info(f"  Request #{i+1} (invalid login): URL: {req.url}, Method: {req.method}, Status: {status_code}")
            if req.method == 'POST' and '/redfish/v1/SessionService/Sessions' in req.url:
                login_post_request = req
                logger.info(f"  *** Identified potential invalid login POST request: {req.url} ***")
                break
        
        if login_post_request and login_post_request.response:
            self.assertIn(login_post_request.response.status_code, [400, 401, 403],
                          f"Expected error status code (400/401/403) for invalid login POST to {login_post_request.url}, "
                          f"got {login_post_request.response.status_code}. "
                          f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500] if login_post_request.response.body else 'N/A'}")
            logger.info(f"Invalid login POST to {login_post_request.url} correctly received error status {login_post_request.response.status_code}.")
        else:
            logger.warning("No specific login POST request found for invalid login, or no network error response. Checking UI for error message.")
            try:
                # Making XPath for error message more generic and case-insensitive
                error_message_xpath = "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'invalid') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'failed') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'unauthorized') or contains(@class, 'error') or contains(@role, 'alert') or contains(@class, 'Mui-error')]"
                error_message = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, error_message_xpath))
                )
                self.assertTrue(error_message.is_displayed())
                logger.info(f"Found UI error message for invalid login: {error_message.text}")
            except TimeoutException:
                page_source_snippet = self.driver.page_source[:1000] if self.driver.page_source else "N/A"
                self.fail(f"Failed to find an error message on the UI after invalid login attempt, AND no conclusive network error was found/identified. Current URL: {self.driver.current_url}. Page source snippet: {page_source_snippet}")


if __name__ == '__main__':
    reports_dir = '.' # Output reports to current directory for Jenkins to pick up
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    # Ensure the report name matches what's expected in Jenkinsfile
    unittest.main(testRunner=HtmlTestRunner.HTMLTestRunner(output=reports_dir, report_name="test_report"))
