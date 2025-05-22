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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

        sw_options = {
            'verify_ssl': False,
            'connection_timeout': 60
        }
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
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"Clearing {len(self.driver.requests)} requests from previous test run.")
            del self.driver.requests
        logger.info(f"Navigating to base URL: {self.base_url}")
        self.driver.get(self.base_url)
        time.sleep(5) # Allow time for page to load and initial requests to complete
        if hasattr(self.driver, 'requests'):
            logger.info(f"Captured {len(self.driver.requests)} requests after navigating to base_url ({self.base_url}):")
            if not self.driver.requests:
                logger.info(" No requests captured by selenium-wire for initial page load.")
            for i, req in enumerate(self.driver.requests):
                status_code = req.response.status_code if req.response else 'No response'
                logger.info(f" Initial Nav Request #{i+1}: URL: {req.url}, Method: {req.method}, Status: {status_code}")
        else:
            logger.error(" self.driver does not have 'requests' attribute. Selenium-wire might not be active.")
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
            username_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            # More generic XPath for the login button
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

            login_button.click()
            logger.info("Clicked login button.")

        except TimeoutException:
            self.fail("Timeout waiting for login elements.")
        except NoSuchElementException:
            self.fail("Could not find login elements (username, password, or button).")
        except Exception as e:
            self.fail(f"Error during login interaction: {e}")

    def test_invalid_credentials(self):
        logger.info(f"Attempting invalid login with user: {USERNAME}, pass: {INVALID_PASSWORD}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        try:
            # Wait for the specific POST request to SessionService/Sessions
            login_request = self.driver.wait_for_request('/redfish/v1/SessionService/Sessions', timeout=10)
            self.assertIsNotNone(login_request, "Login request not captured.")
            self.assertIsNotNone(login_request.response, "Response not captured for login request.")
            logger.info(f"Captured invalid login POST request to {login_request.url} with status: {login_request.response.status_code}")

            self.assertEqual(login_request.response.status_code, 401,
                             f"Invalid login POST to {login_request.url} expected status 401, got {login_request.response.status_code}")

        except TimeoutException:
            self.fail("Timeout waiting for invalid login request to be captured by Selenium Wire.")
        except Exception as e: # Catch any other assertion errors or issues
            self.fail(f"An unexpected error occurred while verifying invalid login: {e}")


    def test_successful_login(self):
        logger.info(f"Attempting successful login with user: {USERNAME}, pass: {PASSWORD}")
        self._perform_login(USERNAME, PASSWORD)

        try:
            # Wait for the specific POST request to SessionService/Sessions
            login_request = self.driver.wait_for_request('/redfish/v1/SessionService/Sessions', timeout=10)
            self.assertIsNotNone(login_request, "Login request not captured.")
            self.assertIsNotNone(login_request.response, "Response not captured for login request.")
            logger.info(f"Captured successful login POST request to {login_request.url} with status: {login_request.response.status_code}")


            self.assertEqual(login_request.response.status_code, 201,  # 201 Created for successful session creation
                             f"Successful login POST to {login_request.url} expected status 201, got {login_request.response.status_code}")

            # Check for redirection to dashboard or presence of a dashboard element
            WebDriverWait(self.driver, 20).until(
                EC.url_contains("/#/dashboard") # Check if URL contains dashboard path
            )
            self.assertIn("/#/dashboard", self.driver.current_url, "Not redirected to dashboard after successful login.")
            logger.info(f"Login appears successful. Current URL: {self.driver.current_url}")

        except TimeoutException:
            self.fail(f"Timeout waiting for successful login validation (request capture or URL change). Current URL: {self.driver.current_url}")
        except Exception as e:
            self.fail(f"An unexpected error occurred while verifying successful login: {e}. Current URL: {self.driver.current_url}")


if __name__ == '__main__':
    logger.info("Starting test execution from __main__...")
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OpenBMCAuthTests))

    # Define the output directory and ensure it exists
    output_dir = "selenium_reports"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Define the full path for the report file
    report_file_path = os.path.join(output_dir, "selenium_webui_report.html")

    logger.info(f"Report will be generated at: {report_file_path}")

    # Open the report file in write mode and run the tests
    with open(report_file_path, 'w') as report_file:
        runner = HtmlTestRunner.HTMLTestRunner(
            stream=report_file,
            title='OpenBMC WebUI Auth Test Report',
            description='Selenium tests for OpenBMC WebUI Authentication',
            verbosity=2 # Or 1 for less verbose
        )
        runner.run(suite)
    logger.info("Test execution finished.")
