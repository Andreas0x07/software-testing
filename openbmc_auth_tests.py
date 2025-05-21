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
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-certificate-errors") 
        
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.base_url = OPENBMC_HOST

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()

    def setUp(self):
        # It's important to get a fresh page for each test
        self.driver.get(self.base_url)
        # Clear requests from previous tests or page loads if necessary
        del self.driver.requests

    def tearDown(self):
        # Clear requests after each test
        if hasattr(self.driver, 'requests'): # Check if requests were even initialized by an action
            del self.driver.requests
        pass

    def _perform_login(self, username, password):
        try:
            # Ensure we're on the login page, or at least a page where these elements exist
            # self.driver.get(self.base_url + "/login") # Or whatever your login page path is, if not root
            
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            # Try to find a common login button. You might need to adjust the XPath.
            # Common patterns: <button type="submit">Log In</button>, <input type="submit" value="Log In">
            # <button ...>Login</button> etc.
            login_button = self.driver.find_element(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')] | //button[@type='submit'] | //input[@type='submit' and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]")


            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Clear requests right before the action that triggers the network call
            del self.driver.requests
            login_button.click()
            
            # Wait for the request to be processed and recorded.
            # Increased sleep slightly for debugging, can be optimized later.
            print("Waiting for login request to be captured...")
            time.sleep(5) 

        except TimeoutException:
            self.fail(f"Login form elements (username, password, or button) not found on page {self.driver.current_url}. Check if you are on the correct login page.")
        except NoSuchElementException:
            self.fail(f"Login form elements (username, password, or button) not found by fallback on page {self.driver.current_url}.")


    def test_successful_login(self):
        """Login with valid credentials and check for successful HTTP response."""
        print(f"Attempting successful login with user: {USERNAME}")
        self._perform_login(USERNAME, PASSWORD)
        
        print(f"Captured {len(self.driver.requests)} requests during/after login attempt:")
        if not self.driver.requests:
            print("No requests were captured by selenium-wire at all.")
        
        login_post_request = None
        for i, req in enumerate(self.driver.requests):
            print(f"Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No response'}")
            if req.response and req.response.body:
                try:
                    # Limit printing of body to avoid huge logs
                    body_snippet = req.response.body.decode('utf-8', errors='ignore')[:200]
                    print(f"  Response Body Snippet: {body_snippet}")
                except Exception as e:
                    print(f"  Error decoding/printing response body: {e}")

            # --- ADJUST THIS CONDITION ---
            # This is the condition we are trying to get right.
            # You need to find the actual login submission request.
            # Example: Check if it's a POST to a specific path like '/login/submit' or '/api/v1/session'
            if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower() or 'token' in req.url.lower()): # Added 'token' as another common keyword
                login_post_request = req
                print(f"*** Identified potential login POST request: {req.url} ***")
                break # Found a candidate
        
        self.assertIsNotNone(login_post_request, "No suitable login POST request (containing 'login', 'session', or 'token' in URL) captured by selenium-wire. Check printed requests above.")
        
        # A successful login POST usually returns 200 OK or 201 Created (for sessions)
        # It might also return a 302 Found if it redirects immediately.
        self.assertIn(login_post_request.response.status_code, [200, 201], 
                      f"Expected successful login status code (200 or 201) on POST {login_post_request.url}, "
                      f"got {login_post_request.response.status_code}. "
                      f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")

        print(f"Successful login POST to {login_post_request.url} confirmed with status {login_post_request.response.status_code}.")

        # Optional: Verify UI change (e.g., URL or element on dashboard)
        try:
            WebDriverWait(self.driver, 10).until(
                EC.url_contains("dashboard") # Or "overview", or other part of your post-login URL
            )
            print(f"Redirected to URL containing 'dashboard': {self.driver.current_url}")
        except TimeoutException:
            self.fail(f"Login network call successful, but did not redirect to a 'dashboard' URL. Current URL: {self.driver.current_url}")


    def test_invalid_credentials(self):
        """Attempt login with invalid credentials and check for failure indication."""
        print(f"Attempting invalid login with user: {USERNAME}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        login_post_request = None
        print(f"Captured {len(self.driver.requests)} requests during/after invalid login attempt:")
        for i, req in enumerate(self.driver.requests):
            print(f"Request #{i+1} (invalid login): URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No response'}")
            if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower() or 'token' in req.url.lower()):
                login_post_request = req
                print(f"*** Identified potential invalid login POST request: {req.url} ***")
                break
        
        if login_post_request and login_post_request.response:
            self.assertIn(login_post_request.response.status_code, [400, 401, 403],
                          f"Expected error status code (400/401/403) for invalid login POST to {login_post_request.url}, "
                          f"got {login_post_request.response.status_code}. "
                          f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")
            print(f"Invalid login POST to {login_post_request.url} correctly received error status {login_post_request.response.status_code}.")
        else:
            print("No specific login POST request found for invalid login, or no response. Checking UI for error message.")
            try:
                error_message = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'invalid credentials') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login failed') or contains(@class, 'error') or contains(@role, 'alert')]"))
                ) # Added more generic error selectors
                self.assertTrue(error_message.is_displayed())
                print(f"Found UI error message for invalid login: {error_message.text}")
            except TimeoutException:
                self.fail("Failed to find an error message on the UI after invalid login attempt, and no conclusive network error found.")

    # @unittest.skip("Skipping account lockout test as it may interfere with other tests")
    # def test_account_lockout(self):
    #    pass # Keep your existing code if you plan to use it

if __name__ == '__main__':
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    unittest.main(testRunner=HtmlTestRunner.HTMLTestRunner(output='.', report_name="test_report"))
