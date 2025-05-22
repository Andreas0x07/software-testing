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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

selenium_wire_logger = logging.getLogger('seleniumwire')
selenium_wire_logger.setLevel(logging.INFO)

OPENBMC_HOST = "https://localhost:2443"
USERNAME = "root"
PASSWORD = "0penBmc"
INVALID_PASSWORD = "invalidpassword"
LOGIN_URL_PATH = "/login"

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

        sw_options = {'verify_ssl': False, 'disable_capture': False}
        cls.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)
        logger.info("WebDriver (Selenium Wire) initialized.")
        
        # Updated logging for proxy address
        if hasattr(cls.driver.backend, 'master') and hasattr(cls.driver.backend.master, 'options'):
            host = cls.driver.backend.master.options.listen_host
            port = cls.driver.backend.master.options.listen_port
            logger.info(f"Selenium Wire proxy (mitmproxy) is listening on: {host}:{port}")
        elif hasattr(cls.driver, 'proxy') and cls.driver.proxy: # Fallback if above not found
             logger.info(f"Selenium Wire proxy is active. Details: {cls.driver.proxy}")
        else:
            logger.info("Selenium Wire proxy is active, but specific address details via master.options were not retrieved.")

    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down OpenBMCAuthTests class...")
        if cls.driver:
            cls.driver.quit()
            logger.info("WebDriver quit.")

    def setUp(self):
        logger.info(f"\n--- Test: {self._testMethodName} ---")
        if hasattr(self.driver, 'requests'):
            del self.driver.requests
        self.driver.get(self.base_url)
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
        logger.info(f"Navigated to {self.base_url} and login page loaded.")
        if hasattr(self.driver, 'requests'):
            del self.driver.requests

    def tearDown(self):
        logger.info(f"--- End Test: {self._testMethodName} ---")

    def _perform_login(self, username, password):
        try:
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")
            login_button_xpath = "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')] | //button[@type='submit'] | //input[@type='submit' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'log in')]"
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, login_button_xpath))
            )
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)

            if hasattr(self.driver, 'requests'):
                del self.driver.requests

            login_button.click()
            logger.info(f"Clicked login button with user: {username}.")
            time.sleep(1) 
        except Exception as e:
            logger.error(f"Error during login interaction: {e}", exc_info=True)
            self.fail(f"Error during login interaction: {e}")

    def _log_s_wire_requests(self, test_phase_description="current"):
        if hasattr(self.driver, 'requests') and self.driver.requests:
            logger.info(f"S-Wire captured {len(self.driver.requests)} requests during {test_phase_description} phase:")
            for i, req in enumerate(self.driver.requests):
                response_status = req.response.status_code if req.response else 'No resp'
                response_body_excerpt = req.response.body[:200].decode('utf-8', 'ignore') if req.response and req.response.body else 'No body'
                logger.info(f" {test_phase_description} S-Wire Req #{i+1}: URL: {req.url}, Method: {req.method}, Status: {response_status}, Body: {response_body_excerpt}")
        else:
            logger.info(f"No S-Wire requests captured by Selenium Wire during {test_phase_description} phase.")

    def test_invalid_credentials(self):
        logger.info(f"Attempting invalid login with user: {USERNAME}, pass: {INVALID_PASSWORD}")
        self._perform_login(USERNAME, INVALID_PASSWORD)

        try:
            logger.info(f"Waiting for S-Wire request to '{LOGIN_URL_PATH}' (timeout 15s)...")
            login_request = self.driver.wait_for_request(LOGIN_URL_PATH, timeout=15)
            self._log_s_wire_requests("invalid_credentials login action")

            self.assertIsNotNone(login_request, f"Login request to {LOGIN_URL_PATH} not captured.")
            self.assertIsNotNone(login_request.response, "Response not captured for login request.")

            logger.info(f"Captured POST to {login_request.url}, Status: {login_request.response.status_code}")
            self.assertEqual(login_request.method, "POST")
            self.assertEqual(login_request.response.status_code, 200,
                             f"Expected status 200 for {LOGIN_URL_PATH}, got {login_request.response.status_code}")

            time.sleep(2)
            current_url = self.driver.current_url
            self.assertNotIn("/#/dashboard", current_url,
                             "User was redirected to dashboard despite invalid credentials.")
            logger.info(f"Invalid login correctly did not redirect to dashboard. Current URL: {current_url}")

        except TimeoutException:
            self._log_s_wire_requests("invalid_credentials timeout")
            self.fail(f"Timeout waiting for login XHR to '{LOGIN_URL_PATH}'.")
        except Exception as e:
            self._log_s_wire_requests("invalid_credentials exception")
            logger.error(f"Unexpected error in test_invalid_credentials: {e}", exc_info=True)
            self.fail(f"Unexpected error in test_invalid_credentials: {e}")

    def test_successful_login(self):
        logger.info(f"Attempting successful login with user: {USERNAME}, pass: {PASSWORD}")
        self._perform_login(USERNAME, PASSWORD)

        try:
            logger.info(f"Waiting for S-Wire request to '{LOGIN_URL_PATH}' (timeout 15s)...")
            login_request = self.driver.wait_for_request(LOGIN_URL_PATH, timeout=15)
            self._log_s_wire_requests("successful_login login action")

            self.assertIsNotNone(login_request, f"Login request to {LOGIN_URL_PATH} not captured.")
            self.assertIsNotNone(login_request.response, "Response not captured for login request.")

            logger.info(f"Captured POST to {login_request.url}, Status: {login_request.response.status_code}")
            self.assertEqual(login_request.method, "POST")
            self.assertEqual(login_request.response.status_code, 200,
                             f"Expected status 200 for {LOGIN_URL_PATH}, got {login_request.response.status_code}")

            logger.info("Login XHR successful (HTTP 200). Waiting for URL to contain '/#/dashboard' (timeout 20s)...")
            WebDriverWait(self.driver, 20).until(EC.url_contains("/#/dashboard"))
            current_url = self.driver.current_url
            self.assertIn("/#/dashboard", current_url, "Not redirected to dashboard after successful login.")
            logger.info(f"Login successful and redirected. Current URL: {current_url}")

        except TimeoutException:
            self._log_s_wire_requests("successful_login timeout")
            self.fail(f"Timeout waiting for login XHR to '{LOGIN_URL_PATH}' or for dashboard redirect.")
        except Exception as e:
            self._log_s_wire_requests("successful_login exception")
            logger.error(f"Unexpected error in test_successful_login: {e}", exc_info=True)
            self.fail(f"Unexpected error in test_successful_login: {e}")

if __name__ == '__main__':
    logger.info("Starting test execution from __main__...")

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(OpenBMCAuthTests)

    output_dir = "selenium_reports"
    report_filename = "selenium_webui_report" 
    report_file_path = os.path.join(output_dir, f"{report_filename}.html")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    logger.info(f"Report will be generated in directory: {output_dir}, with name: {report_filename}.html")

    test_result = None
    try:
        runner = HtmlTestRunner.HTMLTestRunner(
            output=output_dir,
            report_name=report_filename,
            report_title='OpenBMC WebUI Auth Test Report',
            verbosity=2,
            add_timestamp=False 
        )
        test_result = runner.run(suite)
    except Exception as e:
        logger.error(f"CRITICAL: Exception during HtmlTestRunner execution: {e}", exc_info=True)
    finally:
        logger.info("Test execution block finished (finally).")
        if os.path.exists(report_file_path) and os.path.getsize(report_file_path) > 0:
            logger.info(f"SUCCESS: Report file was created at {report_file_path}. Size: {os.path.getsize(report_file_path)} bytes.")
        else:
            logger.error(f"FAILURE: Report file NOT found or is empty at {report_file_path}.")
            if not os.path.exists(output_dir): os.makedirs(output_dir)
            with open(report_file_path, 'w') as f:
                f.write("<html><body><h1>Report Generation Failed or No Tests Were Run</h1></body></html>")
            logger.info(f"Created a placeholder report file at {report_file_path}.")

    if test_result and not test_result.wasSuccessful():
        logger.error("One or more tests FAILED. Exiting with status 1.")
        sys.exit(1)
    elif not test_result: 
        logger.error("Test result object not obtained (runner might have failed). Exiting with status 2.")
        sys.exit(2)
    else: 
        logger.info("All tests passed. Exiting with status 0.")
        sys.exit(0)
