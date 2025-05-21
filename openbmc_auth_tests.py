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
        
        # Ensure chromedriver is in PATH or specify its location
        # For selenium-wire, you initialize it like this:
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.base_url = OPENBMC_HOST

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            cls.driver.quit()

    def setUp(self):
        self.driver.get(self.base_url)
        # Clear requests from previous tests or page loads if necessary
        del self.driver.requests

    def tearDown(self):
        # Clear requests after each test
        del self.driver.requests
        pass

    def _perform_login(self, username, password):
        try:
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Log In')] | //button[@type='submit']") # Common login button texts/types

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Clear requests before the action that triggers the one we want to inspect
            del self.driver.requests
            login_button.click()
            
            # Wait a bit for the request to be processed and recorded
            # WebDriverWait can also be used to wait for a specific condition post-click
            # For example, waiting for URL to change or for a specific request.
            # Here, a short explicit wait is used for simplicity to allow selenium-wire to capture requests.
            time.sleep(3) # Adjust if necessary

        except TimeoutException:
            self.fail("Login form elements (username, password, or button) not found.")
        except NoSuchElementException:
            self.fail("Login form elements (username, password, or button) not found by fallback.")


    def test_successful_login(self):
        """Login with valid credentials and check for successful HTTP response."""
        self._perform_login(USERNAME, PASSWORD)
        
        # Inspect network requests for the login attempt
        # OpenBMC login POST is often to an endpoint like '/login' or an API endpoint
        # For example, it might be '/login/login' or an Redfish session creation.
        # You may need to inspect your OpenBMC's network traffic to find the exact endpoint.
        login_post_request = None
        for req in self.driver.requests:
            # Common login paths: '/login', '/api/login', '/session', '/redfish/v1/SessionService/Sessions'
            # Check for POST requests that seem like login attempts.
            # The exact URL might vary based on OpenBMC version/configuration.
            # Let's assume the login form POSTs to an endpoint containing 'login' or 'session'
            if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower()):
                login_post_request = req
                break
        
        self.assertIsNotNone(login_post_request, "No login POST request captured by selenium-wire.")
        
        # A successful login POST usually returns 200 OK or 201 Created (for sessions)
        # It might also return a 302 Found if it redirects immediately.
        # If it's a 302, the actual success might be confirmed by the location header or subsequent GET.
        # For simplicity, let's check for 200 or 201 on the POST itself.
        self.assertIn(login_post_request.response.status_code, [200, 201], 
                      f"Expected successful login status code (200 or 201) on POST, "
                      f"got {login_post_request.response.status_code} for URL {login_post_request.url}. "
                      f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")

        # Optionally, you can still verify a UI change if desired, as a secondary check:
        # For example, check if the URL changed to a dashboard page
        try:
            WebDriverWait(self.driver, 10).until(
                EC.url_contains("dashboard") # Or "overview", or whatever your main page is
            )
        except TimeoutException:
            self.fail(f"Login seemed successful via network, but did not redirect to a dashboard URL. Current URL: {self.driver.current_url}")
        
        # Or check for a known element on the dashboard page
        # try:
        #     WebDriverWait(self.driver, 10).until(
        #         EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'System Overview')]")) 
        #     )
        # except TimeoutException:
        #     self.fail("Login seemed successful, but 'System Overview' text not found on the dashboard.")


    def test_invalid_credentials(self):
        """Attempt login with invalid credentials and check for failure indication."""
        self._perform_login(USERNAME, INVALID_PASSWORD)

        # For invalid credentials, the UI might show an error message.
        # Alternatively, the login POST request might return an error status (e.g., 400, 401).
        login_post_request = None
        for req in self.driver.requests:
            if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower()):
                login_post_request = req
                break
        
        if login_post_request and login_post_request.response:
            # If the server responds with an error code on the POST itself
            self.assertIn(login_post_request.response.status_code, [400, 401, 403],
                          f"Expected error status code (400/401/403) for invalid login, "
                          f"got {login_post_request.response.status_code} for URL {login_post_request.url}. "
                          f"Response body: {login_post_request.response.body.decode('utf-8', errors='ignore')[:500]}")
        else:
            # Fallback to checking for a UI error message if direct network check is not conclusive
            # This part depends on how your OpenBMC UI displays errors
            try:
                error_message = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'invalid credentials') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login failed')]"))
                )
                self.assertTrue(error_message.is_displayed())
            except TimeoutException:
                self.fail("Failed to find an error message on the UI after invalid login attempt, and no conclusive network error found.")

    # @unittest.skip("Skipping account lockout test as it may interfere with other tests")
    # def test_account_lockout(self):
    #     # This test assumes that multiple failed logins will lock the account.
    #     # The exact number of attempts and lockout behavior is specific to OpenBMC's configuration.
    #     # For demonstration, let's assume 5 failed attempts lock the account.
    #     # You would need to adjust this based on your OpenBMC's security settings.
        
    #     max_attempts = 5 
    #     print(f"Attempting {max_attempts} invalid logins to trigger lockout...")
    #     for i in range(max_attempts):
    #         self.driver.get(self.base_url) # Refresh page for new login attempt
    #         del self.driver.requests # Clear requests for this attempt

    #         print(f"Lockout attempt {i+1}/{max_attempts}")
    #         self._perform_login(USERNAME, INVALID_PASSWORD) # Perform an invalid login
            
    #         # Optionally, check for intermediate failure indicators if needed
    #         # However, the main check is after all attempts

    #     # Now, attempt to login with correct credentials - it should fail if account is locked
    #     print("Attempting login with correct credentials (should be locked out)...")
    #     self.driver.get(self.base_url)
    #     del self.driver.requests
    #     self._perform_login(USERNAME, PASSWORD)

    #     # Check network requests for the login attempt status when account is expected to be locked
    #     locked_login_request = None
    #     for req in self.driver.requests:
    #         if req.method == 'POST' and ('login' in req.url.lower() or 'session' in req.url.lower()):
    #             locked_login_request = req
    #             break
        
    #     self.assertIsNotNone(locked_login_request, "No login POST request captured for lockout check.")
        
    #     # A locked account might return 401 (Unauthorized) or 403 (Forbidden), or perhaps a specific error code/message.
    #     # Status 429 (Too Many Requests) could also be used by some systems.
    #     expected_lockout_codes = [401, 403] 
    #     self.assertIn(locked_login_request.response.status_code, expected_lockout_codes,
    #                   f"Expected lockout status code {expected_lockout_codes}, "
    #                   f"got {locked_login_request.response.status_code} for URL {locked_login_request.url}. "
    #                   f"Response body: {locked_login_request.response.body.decode('utf-8', errors='ignore')[:500]}")
        
    #     print("Account lockout test finished: verified login failure on locked account.")


if __name__ == '__main__':
    # Ensure the 'reports' directory exists
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    # Generate a timestamped HTML report in the 'reports' directory
    # Using HtmlTestRunner for outputting to a file
    # The Jenkinsfile archives 'test_report.html' from the workspace root.
    # So we should output directly to that name.
    unittest.main(testRunner=HtmlTestRunner.HTMLTestRunner(output='.', report_name="test_report"))
