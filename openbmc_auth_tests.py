import unittest
import time
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

# Configure general logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Enable DEBUG logging for Selenium Wire
selenium_wire_logger = logging.getLogger('seleniumwire')
selenium_wire_logger.setLevel(logging.DEBUG)
# You might also want to add a handler if it's not inheriting one that outputs to console:
# stream_handler = logging.StreamHandler()
# stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
# selenium_wire_logger.addHandler(stream_handler)
# selenium_wire_logger.propagate = False # To avoid duplicate messages if root logger also has a handler

OPENBMC_HOST = "https://localhost:2443"
USERNAME = "root"
PASSWORD = "0penBmc"
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
        chrome_options.add_argument("--ignore-certificate-errors")
        # Potentially useful Chrome logging options (might be verbose)
        # chrome_options.add_argument("--enable-logging")
        # chrome_options.add_argument("--v=1")


        sw_options = {
            'verify_ssl': False,
            'connection_timeout': 60,
            'disable_capture': False, # Explicitly ensure capture is enabled
            # 'auto_config': False, # For debugging, you could try disabling auto-config and setting proxy manually
            # 'addr': '127.0.0.1', # Specify address for Selenium Wire proxy
            # 'port': 0 # Specify a port or let it choose dynamically
        }
        cls.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)
        logger.info("WebDriver (Selenium Wire) initialized.")
        # Log the actual proxy address/port selenium-wire is using, if accessible
        if hasattr(cls.driver, 'backend') and hasattr(cls.driver.backend, 'master'):
             logger.info(f"Selenium Wire proxy seems to be running on: {cls.driver.backend.master.address}")


    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down OpenBMCAuthTests class...")
        if cls.driver:
            # Capture any final requests before quitting
            if hasattr(cls.driver, 'requests') and cls.driver.requests:
                logger.info(f"S-Wire Captured {len(cls.driver.requests)} requests before driver quit:")
                for i, req in enumerate(cls.driver.requests):
                    logger.info(f" Final S-Wire Req #{i+1}: URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No resp'}")
                del cls.driver.requests
            cls.driver.quit()
            logger.info("WebDriver quit.")

    def setUp(self):
        logger.info(f"\n--- Test: {self._testMethodName} ---")
        if hasattr(self.driver, 'requests'):
            del self.driver.requests
            logger.info("Cleared previous S-Wire requests at start of setUp.")
        
        logger.info(f"Navigating to base URL: {self.base_url}")
        self.driver.get(self.base_url)
        logger.info(f"Navigation to {self.base_url} initiated. Waiting for page elements...")
        time.sleep(5) 

        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Captured {len(self.driver.requests)} S-Wire requests during/after page load to {self.base_url}:")
            for i, req in enumerate(self.driver.requests):
                status_code = req.response.status_code if req.response else 'No resp'
                logger.info(f" Initial Nav S-Wire Req #{i+1}: URL: {req.url}, Method: {req.method}, Status: {status_code}")
        else:
            logger.info(f"No S-Wire requests captured by selenium-wire during/after page load to {self.base_url}.")
        
        if hasattr(self.driver, 'requests'):
            del self.driver.requests
            logger.info("Cleared S-Wire requests post-navigation, before login action.")


    def tearDown(self):
        logger.info(f"--- In tearDown for: {self._testMethodName} ---")
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Clearing {len(self.driver.requests)} S-Wire requests at end of {self._testMethodName}.")
            for i, req in enumerate(self.driver.requests):
                 logger.info(f" TearDown S-Wire Req #{i+1}: URL: {req.url}, Method: {req.method}, Status: {req.response.status_code if req.response else 'No resp'}")
            del self.driver.requests
        logger.info(f"--- End Test: {self._testMethodName} ---")

    def _perform_login(self, username, password):
        try:
            logger.info(f"Waiting for username field by ID 'username'")
            username_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            logger.info(f"Username field found. Waiting for password field by ID 'password'")
            password_field = self.driver.find_element(By.ID, "password")
            logger.info(f"Password field found.")
            
            login_button_xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')] | //button[@type='submit'] | //input[@type='submit' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]"
            logger.info(f"Waiting for login button with XPath: {login_button_xpath}")
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            logger.info(f"Login button found and clickable.")

            username_field.clear()
            username_field.send_keys(username)
            logger.info(f"Entered username.")
            password_field.clear()
            password_field.send_keys(password)
            logger.info(f"Entered password.")

            logger.info("Clearing S-Wire requests immediately before clicking login button...")
            if hasattr(self.driver, 'requests'):
                del self.driver.requests
            
            logger.info("Clicking login button...")
            login_button.click()
            logger.info("Clicked login button. Waiting briefly (3s) for XHR to initiate and for S-Wire to process...")
            time.sleep(3) 

        except TimeoutException as te:
            logger.error(f"Timeout waiting for login elements: {te}")
            self.fail(f"Timeout waiting for login elements. Page source: \n{self.driver.page_source[:2000]}")
        except NoSuchElementException as nse:
            logger.error(f"Could not find login elements (username, password, or button): {nse}")
            self.fail(f"Could not find login elements. Page source: \n{self.driver.page_source[:2000]}")
        except Exception as e:
            logger.error(f"Error during login interaction: {e}")
            self.fail(f"Error during login interaction: {e}. Page source: \n{self.driver.page_source[:2000]}")

    def _log_s_wire_requests(self, test_phase_description="current"):
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"S-Wire captured {len(self.driver.requests)} requests during {test_phase_description} phase:")
            for i, req in enumerate(self.driver.requests):
                logger.info(f" {test_phase_description} S-Wire Req #{i+1}: URL: {req.url}, Method: {req.method}, Headers: {req.headers}, Status: {req.response.status_code if req.response else 'No resp'}")
        else:
            logger.info(f"No S-Wire requests captured by Selenium Wire during {test_phase_description} phase.")


    def test_invalid_credentials(self):
        logger.info(f"Attempting invalid login with user: {USERNAME}, pass: {INVALID_PASSWORD}")
        self._perform_login(USERNAME, INVALID_PASSWORD)
        self._log_s_wire_requests("invalid_credentials login action")

        try:
            logger.info("Waiting for S-Wire request to '/redfish/v1/SessionService/Sessions' (timeout 15s)...")
            login_request = self.driver.wait_for_request('/redfish/v1/SessionService/Sessions', timeout=15)
            self.assertIsNotNone(login_request, "Login request (XHR) not captured by Selenium Wire.")
            self.assertIsNotNone(login_request.response, "Response not captured for login request by Selenium Wire.")
            logger.info(f"Captured invalid login POST request to {login_request.url} with status: {login_request.response.status_code}")
            self.assertEqual(login_request.response.status_code, 401,
                             f"Invalid login POST to {login_request.url} expected status 401, got {login_request.response.status_code}")
        except TimeoutException:
            logger.error("Timeout waiting for invalid login XHR to be captured by Selenium Wire.")
            self._log_s_wire_requests("invalid_credentials timeout") # Log requests again on timeout
            self.fail("Timeout waiting for invalid login XHR to be captured by Selenium Wire.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while verifying invalid login: {e}")
            self._log_s_wire_requests("invalid_credentials exception")
            self.fail(f"An unexpected error occurred while verifying invalid login: {e}")

    def test_successful_login(self):
        logger.info(f"Attempting successful login with user: {USERNAME}, pass: {PASSWORD}")
        self._perform_login(USERNAME, PASSWORD)
        self._log_s_wire_requests("successful_login login action")

        try:
            logger.info("Waiting for S-Wire request to '/redfish/v1/SessionService/Sessions' (timeout 15s)...")
            login_request = self.driver.wait_for_request('/redfish/v1/SessionService/Sessions', timeout=15)
            self.assertIsNotNone(login_request, "Login request (XHR) not captured by Selenium Wire.")
            self.assertIsNotNone(login_request.response, "Response not captured for login request by Selenium Wire.")
            logger.info(f"Captured successful login POST request to {login_request.url} with status: {login_request.response.status_code}")
            self.assertEqual(login_request.response.status_code, 201,
                             f"Successful login POST to {login_request.url} expected status 201, got {login_request.response.status_code}")

            logger.info("Login XHR successful. Waiting for URL to contain '/#/dashboard' (timeout 20s)...")
            WebDriverWait(self.driver, 20).until(EC.url_contains("/#/dashboard"))
            self.assertIn("/#/dashboard", self.driver.current_url, "Not redirected to dashboard after successful login.")
            logger.info(f"Login successful and redirected. Current URL: {self.driver.current_url}")
        except TimeoutException:
            logger.error(f"Timeout waiting for successful login validation (XHR capture or URL change). Current URL: {self.driver.current_url}")
            self._log_s_wire_requests("successful_login timeout") # Log requests again on timeout
            self.fail(f"Timeout waiting for successful login validation. Current URL: {self.driver.current_url}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while verifying successful login: {e}. Current URL: {self.driver.current_url}")
            self._log_s_wire_requests("successful_login exception")
            self.fail(f"An unexpected error occurred while verifying successful login: {e}. Current URL: {self.driver.current_url}")

if __name__ == '__main__':
    logger.info("Starting test execution from __main__...")
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OpenBMCAuthTests))

    output_dir = "selenium_reports"
    if not os.path.exists(output_dir):
        logger.info(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir)
    
    report_file_path = os.path.join(output_dir, "selenium_webui_report.html")
    logger.info(f"Report will be generated at: {report_file_path}")
    
    test_result = None
    try:
        with open(report_file_path, 'w') as report_file:
            runner = HtmlTestRunner.HTMLTestRunner(
                stream=report_file,
                title='OpenBMC WebUI Auth Test Report',
                description='Selenium tests for OpenBMC WebUI Authentication',
                verbosity=2
            )
            logger.info("Running tests with HtmlTestRunner...")
            test_result = runner.run(suite)
            logger.info("HtmlTestRunner finished.")
    except Exception as e:
        logger.error(f"CRITICAL: Exception during test running or HtmlTestRunner report generation: {e}", exc_info=True)
        try:
            with open(report_file_path, 'w') as report_file:
                report_file.write(f"<html><body><h1>Test Execution Error</h1><p>Failed to generate full report due to: {e}</p></body></html>")
            logger.info(f"Wrote minimal error report to {report_file_path}")
        except Exception as e_minimal:
            logger.error(f"CRITICAL: Failed even to write minimal error report: {e_minimal}", exc_info=True)
    finally:
        logger.info("Test execution block finished (finally).")
        if os.path.exists(report_file_path) and os.path.getsize(report_file_path) > 0:
            logger.info(f"SUCCESS: Report file was created at {report_file_path}. Size: {os.path.getsize(report_file_path)} bytes.")
        else:
            logger.error(f"FAILURE: Report file NOT found or is empty at {report_file_path} after test execution attempt.")
            if not os.path.exists(output_dir): os.makedirs(output_dir) 
            with open(report_file_path, 'w') as f: f.write("<html><body><h1>Report Generation Failed</h1><p>Test script completed, but no report was generated or it was empty.</p></body></html>")
            logger.info(f"Created a placeholder report file at {report_file_path} because the original was missing/empty.")

    if test_result and not test_result.wasSuccessful():
        logger.error("One or more tests FAILED. Exiting with status 1.")
        sys.exit(1)
    elif not test_result:
        logger.error("Test result not obtained (likely critical error before tests ran). Exiting with status 2.")
        sys.exit(2)
    else:
        logger.info("All tests passed. Exiting with status 0.")
        sys.exit(0)
