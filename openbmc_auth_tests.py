import unittest
import time
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import HtmlTestRunner as html_testRunner  # Corrected import

OPENBMC_URL = 'https://localhost:2443'
VALID_USERNAME = 'root'
VALID_PASSWORD = '0penBmc'
INVALID_PASSWORD = 'wrongpassword'
LOCKOUT_ATTEMPTS = 3
WAIT_TIMEOUT = 15

LOGIN_API_PATH_PART = '/redfish/v1/SessionService/Sessions'
EXPECTED_INVALID_LOGIN_STATUS = 401
EXPECTED_LOCKED_OUT_STATUS = 401

class OpenBMCAuthTests(unittest.TestCase):
    def setUp(self):
        chrome_options = Options()
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--start-maximized")

        sw_options = {'verify_ssl': False}
        self.driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=sw_options)

        self.driver.get(OPENBMC_URL)
        try:
            WebDriverWait(self.driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, 'username'))
            )
        except TimeoutException:
            self.driver.quit()
            self.fail(f"Failed to load login page (initial load)")
        del self.driver.requests
        self.driver.delete_all_cookies()
        self.driver.refresh()
        try:
            WebDriverWait(self.driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, 'username'))
            )
        except TimeoutException:
            self.driver.quit()
            self.fail(f"Failed to reload login page")
        del self.driver.requests

    def _perform_login(self, username, password):
        try:
            user_field = WebDriverWait(self.driver, WAIT_TIMEOUT).until(EC.element_to_be_clickable((By.ID, 'username')))
            user_field.clear()
            user_field.send_keys(username)

            pass_field = WebDriverWait(self.driver, WAIT_TIMEOUT).until(EC.element_to_be_clickable((By.ID, 'password')))
            pass_field.clear()
            pass_field.send_keys(password)

            login_button = WebDriverWait(self.driver, WAIT_TIMEOUT).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-test-id="login-button-submit"]')))
            login_button.click()
        except Exception as e:
            self.fail(f"Login interaction failed: {type(e).__name__} - {e}")

    def test_successful_login(self):
        del self.driver.requests
        self._perform_login(VALID_USERNAME, VALID_PASSWORD)
        try:
            dash_locator = (By.ID, 'main-content')
            WebDriverWait(self.driver, WAIT_TIMEOUT).until(
                EC.visibility_of_element_located(dash_locator)
            )
            self.assertTrue(self.driver.find_element(*dash_locator).is_displayed())
        except Exception as e:
            self.fail(f"Successful login failed validation: {type(e).__name__}")

    def test_invalid_credentials(self):
        del self.driver.requests
        self._perform_login(VALID_USERNAME, INVALID_PASSWORD)
        try:
            login_request = self.driver.wait_for_request(LOGIN_API_PATH_PART, timeout=10)
            self.assertIsNotNone(login_request.response)
            self.assertEqual(login_request.response.status_code, EXPECTED_INVALID_LOGIN_STATUS)
        except TimeoutException:
            self.fail(f"Login request not detected")
        except Exception as e:
            self.fail(f"Network check failed: {type(e).__name__} - {e}")
        try:
            WebDriverWait(self.driver, 2).until(EC.presence_of_element_located((By.ID, 'username')))
        except TimeoutException:
            self.fail("Not on login page after invalid attempt")
            '''
    def test_account_lockout(self):
        for i in range(LOCKOUT_ATTEMPTS):
            del self.driver.requests
            self._perform_login(VALID_USERNAME, INVALID_PASSWORD)
            try:
                login_request = self.driver.wait_for_request(LOGIN_API_PATH_PART, timeout=10)
                self.assertIsNotNone(login_request.response)
                self.assertEqual(login_request.response.status_code, EXPECTED_INVALID_LOGIN_STATUS)
                WebDriverWait(self.driver, WAIT_TIMEOUT).until(EC.presence_of_element_located((By.ID, 'username')))
                time.sleep(0.2)
            except Exception as e:
                self.fail(f"Failure during lockout attempt {i + 1}: {type(e).__name__} - {e}")

        del self.driver.requests
        self._perform_login(VALID_USERNAME, VALID_PASSWORD)
        try:
            lockout_check_request = self.driver.wait_for_request(LOGIN_API_PATH_PART, timeout=10)
            self.assertIsNotNone(lockout_check_request.response)
            self.assertEqual(lockout_check_request.response.status_code, EXPECTED_LOCKED_OUT_STATUS,
                             f"Observed status {lockout_check_request.response.status_code}, expected {EXPECTED_LOCKED_OUT_STATUS} (lockout)")
        except Exception as e:
            self.fail(f"Final lockout check failed: {type(e).__name__} - {e}")
'''
    def tearDown(self):
        if self.driver:
            self.driver.quit()

if __name__ == '__main__':
    with open('test_report.html', 'w') as f:
        runner = html_testRunner.HTMLTestRunner(
            stream=f,
            report_title='OpenBMC WebUI Test Report',  # Changed 'title' to 'report_title'
            verbosity=2
        )
        unittest.main(testRunner=runner, exit=False)
