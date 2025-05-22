import unittest
import time
import json
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import HtmlTestRunner
import os
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout # Ensure logs go to stdout for Jenkins
)
logger = logging.getLogger(__name__)

# Reduce verbosity of seleniumwire's internal logger for cleaner Jenkins logs
selenium_wire_logger = logging.getLogger('seleniumwire')
selenium_wire_logger.setLevel(logging.WARNING)


OPENBMC_HOST = "https://localhost:2443"
USERNAME = "root"
PASSWORD = "0penBmc"
INVALID_PASSWORD = "invalidpassword"
# This is the API path that handles the login POST request
API_LOGIN_PATH_PART = '/redfish/v1/SessionService/Sessions'
DASHBOARD_URL_PART = "/#/dashboard"

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
        chrome_options.add_argument("--ignore-certificate-errors")

        # Explicitly tell Selenium Wire where to find the backend mitmproxy executable if needed
        # This is usually handled automatically if mitmproxy is in PATH within the Docker container
        sw_options = {
            'verify_ssl': False,
            'disable_capture': False,
            # 'mitm_path': '/path/to/mitmproxy' # Only if mitmproxy isn't in PATH
        }
        cls.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)
        logger.info("WebDriver (Selenium Wire) initialized.")

        proxy_address_logged = False
        if hasattr(cls.driver, 'backend') and cls.driver.backend and \
           hasattr(cls.driver.backend, 'master') and cls.driver.backend.master and \
           hasattr(cls.driver.backend.master, 'options'):
            host = cls.driver.backend.master.options.listen_host
            port = cls.driver.backend.master.options.listen_port
            if host and port:
                logger.info(f"Selenium Wire proxy (mitmproxy) is listening on: {host}:{port}")
                proxy_address_logged = True
        
        if not proxy_address_logged and hasattr(cls.driver, 'proxy') and cls.driver.proxy:
            logger.info(f"Selenium Wire proxy is active. Details: {cls.driver.proxy}")
        elif not proxy_address_logged:
            logger.info("Selenium Wire proxy is active, but specific address details were not retrieved.")


    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down OpenBMCAuthTests class...")
        if cls.driver:
            cls.driver.quit()
            logger.info("WebDriver quit.")

    def setUp(self):
        logger.info(f"\n--- Test: {self._testMethodName} ---")
        # Clear requests from previous test if any
        if hasattr(self.driver, 'requests'):
            del self.driver.requests
        
        self.driver.get(self.base_url) # OPENBMC_HOST
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
        logger.info(f"Navigated to {self.base_url} and login page loaded.")
        # Clear any requests made during page load before the actual test action
        if hasattr(self.driver, 'requests'):
            del self.driver.requests


    def tearDown(self):
        logger.info(f"--- End Test: {self._testMethodName} ---")

    def _perform_login(self, username, password):
        try:
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")
            
            # Using a more general XPath for the login button
            login_button_xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in') or @type='submit' or contains(@data-test-id, 'login-button')]"
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)

            # Clear requests before clicking login to isolate the login API call
            if hasattr(self.driver, 'requests'):
                del self.driver.requests

            login_button.click()
            logger.info(f"Clicked login button with user: {username}.")
            # Small delay to ensure request is initiated
            time.sleep(0.5) 
        except Exception as e:
            logger.error(f"Error during login interaction: {e}", exc_info=True)
            # Capture a screenshot on error during login interaction for debugging
            self.driver.save_screenshot(f"{self._testMethodName}_login_interaction_error.png")
            self.fail(f"Error during login interaction: {e}")

    def _log_s_wire_requests(self, test_phase_description="current"):
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Selenium Wire captured {len(self.driver.requests)} request(s) during '{test_phase_description}' phase:")
            for i, req in enumerate(self.driver.requests):
                response_status = req.response.status_code if req.response else 'No response'
                # Limit body size in logs
                response_body_excerpt = ''
                if req.response and req.response.body:
                    try:
                        response_body_excerpt = req.response.body[:200].decode('utf-8', 'ignore')
                    except Exception:
                        response_body_excerpt = '(binary or non-UTF8 data)'
                elif req.response and not req.response.body:
                     response_body_excerpt = 'Empty body'
                else:
                    response_body_excerpt = 'No body in response object'

                logger.info(f"  Req #{i+1}: URL: {req.url}, Method: {req.method}, Status: {response_status}, Resp Body Excerpt: {response_body_excerpt}")
        else:
            logger.info(f"No Selenium Wire requests captured (or already cleared) for '{test_phase_description}' phase.")

    def test_invalid_credentials(self):
        logger.info(f"Attempting invalid login with user: {USERNAME}, pass: {INVALID_PASSWORD}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        try:
            logger.info(f"Waiting for API request containing '{API_LOGIN_PATH_PART}' (timeout 15s)...")
            # This is the crucial request that actually performs the login.
            login_api_request = self.driver.wait_for_request(API_LOGIN_PATH_PART, timeout=15)
            
            self._log_s_wire_requests("invalid_credentials_api_call")

            self.assertIsNotNone(login_api_request, f"Login API request to '{API_LOGIN_PATH_PART}' not captured.")
            self.assertEqual(login_api_request.method, "POST", "Login API request was not a POST.")
            self.assertIsNotNone(login_api_request.response, "Response not captured for login API request.")
            
            logger.info(f"Captured API request to {login_api_request.url}, Method: {login_api_request.method}, Status: {login_api_request.response.status_code}")
            self.assertEqual(login_api_request.response.status_code, 401,
                             f"Expected status 401 for invalid login API call, got {login_api_request.response.status_code}. Body: {login_api_request.response.body[:200].decode('utf-8','ignore') if login_api_request.response.body else 'N/A'}")

            # After a failed API login, check that we are still on the login page (or redirected to it)
            # Give a moment for any redirection to settle
            time.sleep(2) 
            current_url = self.driver.current_url
            self.assertNotIn(DASHBOARD_URL_PART, current_url,
                             "User was redirected to dashboard despite invalid credentials.")
            # Also check that the login form elements are still present
            self.assertTrue(self.driver.find_element(By.ID, "username").is_displayed(), "Username field not found after invalid login.")
            logger.info(f"Invalid login correctly did not redirect to dashboard. Current URL: {current_url}")

        except TimeoutException:
            self._log_s_wire_requests("invalid_credentials_timeout")
            self.driver.save_screenshot("invalid_credentials_timeout.png")
            self.fail(f"Timeout waiting for login API request to '{API_LOGIN_PATH_PART}'.")
        except Exception as e:
            self._log_s_wire_requests("invalid_credentials_exception")
            self.driver.save_screenshot("invalid_credentials_exception.png")
            logger.error(f"Unexpected error in test_invalid_credentials: {e}", exc_info=True)
            self.fail(f"Unexpected error in test_invalid_credentials: {e}")

    def test_successful_login(self):
        logger.info(f"Attempting successful login with user: {USERNAME}, pass: {PASSWORD}")
        self._perform_login(USERNAME, PASSWORD)

        try:
            logger.info(f"Waiting for API request containing '{API_LOGIN_PATH_PART}' (timeout 15s)...")
            login_api_request = self.driver.wait_for_request(API_LOGIN_PATH_PART, timeout=15)

            self._log_s_wire_requests("successful_login_api_call")

            self.assertIsNotNone(login_api_request, f"Login API request to '{API_LOGIN_PATH_PART}' not captured.")
            self.assertEqual(login_api_request.method, "POST", "Login API request was not a POST.")
            self.assertIsNotNone(login_api_request.response, "Response not captured for login API request.")

            logger.info(f"Captured API request to {login_api_request.url}, Method: {login_api_request.method}, Status: {login_api_request.response.status_code}")
            # Successful session creation can be 200 or 201
            self.assertIn(login_api_request.response.status_code, [200, 201],
                          f"Expected status 200 or 201 for successful login API call, got {login_api_request.response.status_code}. Body: {login_api_request.response.body[:200].decode('utf-8','ignore') if login_api_request.response.body else 'N/A'}")

            logger.info(f"Login API call successful. Waiting for URL to contain '{DASHBOARD_URL_PART}' (timeout 20s)...")
            WebDriverWait(self.driver, 20).until(EC.url_contains(DASHBOARD_URL_PART))
            current_url = self.driver.current_url
            self.assertIn(DASHBOARD_URL_PART, current_url, "Not redirected to dashboard after successful login.")
            logger.info(f"Login successful and redirected. Current URL: {current_url}")

        except TimeoutException:
            self._log_s_wire_requests("successful_login_timeout")
            self.driver.save_screenshot("successful_login_timeout.png")
            self.fail(f"Timeout waiting for login API request ('{API_LOGIN_PATH_PART}') or for dashboard redirect ('{DASHBOARD_URL_PART}').")
        except Exception as e:
            self._log_s_wire_requests("successful_login_exception")
            self.driver.save_screenshot("successful_login_exception.png")
            logger.error(f"Unexpected error in test_successful_login: {e}", exc_info=True)
            self.fail(f"Unexpected error in test_successful_login: {e}")

if __name__ == '__main__':
    logger.info("Starting test execution from __main__...")

    # Ensure the output directory exists
    output_dir = os.path.join(os.getcwd(), "selenium_reports") # Use workspace relative path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Created output directory: {output_dir}")
    
    report_filename = "selenium_webui_report" 
    # HtmlTestRunner needs the directory path for 'output' and just the name for 'report_name'
    
    logger.info(f"Report will be generated in directory: {output_dir}, with name: {report_filename}.html")

    # Load tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(OpenBMCAuthTests)
    
    test_result = None # Initialize test_result

    try:
        # Pass the output directory to HtmlTestRunner
        runner = HtmlTestRunner.HTMLTestRunner(
            output=output_dir, # Directory
            report_name=report_filename, # Name of the file, .html will be added
            report_title='OpenBMC WebUI Auth Test Report',
            combine_reports=False, # Generates a single file
            verbosity=2,
            add_timestamp=True # Add timestamp to report name if combine_reports is True and multiple suites
        )
        test_result = runner.run(suite)
    except Exception as e:
        logger.error(f"CRITICAL: Exception during HtmlTestRunner execution: {e}", exc_info=True)
    finally:
        logger.info("Test execution block finished (finally).")
        # Construct the full path to the expected report file
        # HtmlTestRunner might add a timestamp if not controlled properly,
        # but with combine_reports=False and add_timestamp=False (or default behavior for single run)
        # it should be predictable. Let's list files to be sure or use the known name.
        
        # Check for the specific file
        expected_report_file = os.path.join(output_dir, f"{report_filename}.html")
        # HtmlTestRunner might add timestamp if report_name is not unique and combine_reports=True (not our case)
        # or if add_timestamp is True. Default for add_timestamp is False.

        if os.path.exists(expected_report_file) and os.path.getsize(expected_report_file) > 0:
            logger.info(f"SUCCESS: Report file was created at {expected_report_file}. Size: {os.path.getsize(expected_report_file)} bytes.")
        else:
            # Fallback: list files in directory if exact name not found
            found_reports = [f for f in os.listdir(output_dir) if f.startswith(report_filename) and f.endswith(".html")]
            if found_reports:
                 logger.info(f"SUCCESS: Report file(s) found: {', '.join(found_reports)} in {output_dir}")
            else:
                logger.error(f"FAILURE: Report file NOT found or is empty starting with {report_filename} in {output_dir}.")
                # Create a placeholder if no report was generated
                if not os.path.exists(expected_report_file):
                    with open(expected_report_file, 'w') as f:
                        f.write("<html><body><h1>Report Generation Failed or No Tests Were Run</h1></body></html>")
                    logger.info(f"Created a placeholder report file at {expected_report_file}.")

    exit_code = 0
    if test_result:
        if not test_result.wasSuccessful():
            logger.error("One or more tests FAILED. Exiting with status 1.")
            exit_code = 1
        else:
            logger.info("All tests passed. Exiting with status 0.")
            exit_code = 0
    else:
        logger.error("Test result object not obtained (runner might have failed). Exiting with status 2.")
        exit_code = 2
    
    sys.exit(exit_code)
