import unittest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import HtmlTestRunner
import os

# Configuration
OPENBMC_HOST = "https://localhost:2443" 
USERNAME = "root"
PASSWORD = "0penBmc" # Default OpenBMC password
INVALID_PASSWORD = "invalidpassword"

class OpenBMCAuthTests(unittest.TestCase):
    driver = None

    @classmethod
    def setUpClass(cls):
        print("Setting up OpenBMCAuthTests class...")
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-certificate-errors") # Browser ignores cert errors from server
        
        # Selenium-wire specific options could be added here if needed, e.g.:
        # sw_options = {
        #     'verify_ssl': False  # Instructs selenium-wire's proxy to ignore SSL errors from upstream server
        # }
        # cls.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)
        
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.base_url = OPENBMC_HOST
        print("WebDriver initialized.")

    @classmethod
    def tearDownClass(cls):
        print("Tearing down OpenBMCAuthTests class...")
        if cls.driver:
            cls.driver.quit()
            print("WebDriver quit.")

    def setUp(self):
        print(f"\n--- Test: {self._testMethodName} ---")
        # Clear requests from a previous test run, if any existed
        if hasattr(self.driver, 'requests') and self.driver.requests:
            print(f"Clearing {len(self.driver.requests)} requests from previous test.")
            del self.driver.requests
        
        print(f"Navigating to base URL: {self.base_url}")
        self.driver.get(self.base_url)
        # Allow time for page to load and selenium-wire to capture the initial request(s)
        time.sleep(3) 
        
        if hasattr(self.driver, 'requests'):
            print(f"Captured {len(self.driver.requests)} requests after navigating to base_url ({self.base_url}):")
            if not self.driver.requests:
                print("  No requests captured by selenium-wire for initial page load.")
            for i, req in enumerate(self.driver.requests):
                print(f"  Initial Nav Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No resp'}")
        else:
            print("  self.driver does not have 'requests' attribute after initial get(). Selenium-wire might not be active.")

        # Clear requests captured during page load, so we only see requests from login action
        print("Clearing requests before performing login action...")
        del self.driver.requests


    def tearDown(self):
        if hasattr(self.driver, 'requests') and self.driver.requests:
            print(f"Clearing {len(self.driver.requests)} requests at end of {self._testMethodName}.")
            del self.driver.requests
        print(f"--- End Test: {self._testMethodName} ---")


    def _perform_login(self, username, password):
        try:
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            login_button = self.driver.find_element(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')] | //button[@type='submit'] | //input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]")

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            print("Clearing requests immediately before clicking login button...")
            del self.driver.requests # Ensure we only capture post-click requests
            
            print("Clicking login button...")
            login_button.click()
            
            print("Waiting for login action's network request to be captured...")
            time.sleep(5) 

        except TimeoutException:
            self.fail(f"Login form elements (username, password, or button) not found on page {self.driver.current_url}. Current page title: '{self.driver.title}'. Check if you are on the correct login page.")
        except NoSuchElementException:
            self.fail(f"Login form elements (username, password, or button) not found by fallback on page {self.driver.current_url}. Current page title: '{self.driver.title}'.")


    def test_successful_login(self):
        """Login with valid credentials and check for successful HTTP response."""
        print(f"Attempting successful login with user: {USERNAME}")
        self._perform_login(USERNAME, PASSWORD)
        
        if not hasattr(self.driver, 'requests'):
            self.fail("self.driver has no 'requests' attribute after login attempt. Selenium-wire problem.")

        print(f"Captured {len(self.driver.requests)} requests during/after successful login attempt:")
        if not self.driver.requests:
            print("  No requests were captured by selenium-wire at all after login click.")
        
        login_post_request = None
        for i, req in enumerate(self.driver.requests):
            print(f"  Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No response'}")
            if req.response and req.response.body:
                try:
                    body_snippet = req.response.body.decode('utf-8', errors='ignore')[:200]
                    print(f"    Response Body Snippet: {body_snippet}")
                except Exception as e:
                    print(f"    Error decoding/printing response body: {e}")

            if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower() or 'token' in req.url.lower() or '/api/account/login' in req.url): # More specific example
                login_post_request = req
                print(f"  *** Identified potential login POST request: {req.url} ***")
                break 
        
        self.assertIsNotNone(login_post_request, "No suitable login POST request captured. Check printed requests above to identify the correct one and adjust the condition.")
        
        self.assertIn(login_post_request.response.status_code, [200, 201], 
                      f"Expected successful login status code (200 or 201) on POST {login_post_request.url}, "
                      f"got {login_post_request.response.status_code}. "
                      f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")

        print(f"Successful login POST to {login_post_request.url} confirmed with status {login_post_request.response.status_code}.")

        try:
            WebDriverWait(self.driver, 10).until(EC.url_contains("dashboard"))
            print(f"Redirected to URL containing 'dashboard': {self.driver.current_url}")
        except TimeoutException:
            self.fail(f"Login network call successful, but did not redirect to a 'dashboard' URL. Current URL: {self.driver.current_url}")


    def test_invalid_credentials(self):
        """Attempt login with invalid credentials and check for failure indication."""
        print(f"Attempting invalid login with user: {USERNAME}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        if not hasattr(self.driver, 'requests'):
            self.fail("self.driver has no 'requests' attribute after invalid login attempt. Selenium-wire problem.")

        login_post_request = None
        print(f"Captured {len(self.driver.requests)} requests during/after invalid login attempt:")
        if not self.driver.requests:
            print("  No requests were captured by selenium-wire at all after invalid login click.")

        for i, req in enumerate(self.driver.requests):
            print(f"  Request #{i+1} (invalid login): URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No response'}")
            if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower() or 'token' in req.url.lower() or '/api/account/login' in req.url):
                login_post_request = req
                print(f"  *** Identified potential invalid login POST request: {req.url} ***")
                break
        
        if login_post_request and login_post_request.response:
            self.assertIn(login_post_request.response.status_code, [400, 401, 403],
                          f"Expected error status code (400/401/403) for invalid login POST to {login_post_request.url}, "
                          f"got {login_post_request.response.status_code}. "
                          f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")
            print(f"Invalid login POST to {login_post_request.url} correctly received error status {login_post_request.response.status_code}.")
        else:
            print("No specific login POST request found for invalid login, or no error response via network. Checking UI for error message.")
            try:
                error_message = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'invalid credentials') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login failed') or contains(@class, 'error') or contains(@role, 'alert')]"))
                )
                self.assertTrue(error_message.is_displayed())
                print(f"Found UI error message for invalid login: {error_message.text}")
            except TimeoutException:
                self.fail("Failed to find an error message on the UI after invalid login attempt, AND no conclusive network error was found/identified.")


if __name__ == '__main__':
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    unittest.main(testRunner=HtmlTestRunner.HTMLTestRunner(output='.', report_name="test_report"))
