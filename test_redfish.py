import pytest
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BMC_URL = "https://localhost:2443"
AUTH_URL = f"{BMC_URL}/redfish/v1/SessionService/Sessions"
SYSTEM_URL = f"{BMC_URL}/redfish/v1/Systems/system"
RESET_URL = f"{BMC_URL}/redfish/v1/Systems/system/Actions/ComputerSystem.Reset"
CREDENTIALS = {"UserName": "root", "Password": "0penBmc"}
REQUEST_TIMEOUT = 60 # Increased timeout to 60 seconds

@pytest.fixture(scope="session")
def session_token():
    logger.info(f"Creating session for tests. Timeout: {REQUEST_TIMEOUT}s")
    try:
        response = requests.post(
            AUTH_URL,
            json=CREDENTIALS,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
            verify=False
        )
        logger.info(f"Session creation attempt status: {response.status_code}")
        response.raise_for_status()
        token = response.headers.get("X-Auth-Token")
        if not token:
            logger.error("Response body for failed token: %s", response.text)
            pytest.fail("No X-Auth-Token found in response headers")
        logger.info("Session token created successfully.")
        yield token
    except requests.RequestException as e:
        logger.error(f"Failed to create session: {e}")
        logger.error(f"Response body (if available): {e.response.text if e.response else 'No response object'}")
        pytest.fail(f"Session creation failed: {e}")

def test_authentication():
    logger.info(f"Running authentication test. Timeout: {REQUEST_TIMEOUT}s")
    try:
        response = requests.post(
            AUTH_URL,
            json=CREDENTIALS,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
            verify=False
        )
        logger.info(f"Authentication attempt status: {response.status_code}")
        assert response.status_code in (200, 201), f"Expected status 200 or 201, got {response.status_code}. Response: {response.text}"
        assert "X-Auth-Token" in response.headers, "Session token missing in response headers"
        logger.info("Authentication test passed")
    except requests.RequestException as e:
        logger.error(f"Authentication request failed: {e}")
        logger.error(f"Response body (if available): {e.response.text if e.response else 'No response object'}")
        pytest.fail(f"Authentication request failed: {e}")

def test_get_system_info(session_token):
    logger.info(f"Running system information test. Timeout: {REQUEST_TIMEOUT}s")
    headers = {"X-Auth-Token": session_token}
    try:
        response = requests.get(SYSTEM_URL, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        logger.info(f"Get system info status: {response.status_code}")
        assert response.status_code == 200, f"Expected status 200, got {response.status_code}. Response: {response.text}"
        data = response.json()
        assert "Status" in data, "Status field missing in response"
        assert "PowerState" in data, "PowerState field missing in response"
        logger.info("System information test passed")
    except requests.RequestException as e:
        logger.error(f"System info request failed: {e}")
        logger.error(f"Response body (if available): {e.response.text if e.response else 'No response object'}")
        pytest.fail(f"System info request failed: {e}")

def test_power_management(session_token):
    logger.info(f"Running power management test. Timeout: {REQUEST_TIMEOUT}s")
    headers = {"X-Auth-Token": session_token}
    try:
        initial_response = requests.get(SYSTEM_URL, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        logger.info(f"Initial get system info status: {initial_response.status_code}")
        assert initial_response.status_code == 200, f"Expected status 200, got {initial_response.status_code}. Response: {initial_response.text}"

        reset_response = requests.post(
            RESET_URL,
            json={"ResetType": "On"},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            verify=False
        )
        logger.info(f"Reset action status: {reset_response.status_code}")
        assert reset_response.status_code in (200, 202, 204), f"Expected status 200/202/204, got {reset_response.status_code}. Response: {reset_response.text}"

        logger.info("Waiting 15 seconds after reset action...")
        import time
        time.sleep(15) # Increased sleep after reset

        updated_response = requests.get(SYSTEM_URL, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
        logger.info(f"Updated get system info status: {updated_response.status_code}")
        assert updated_response.status_code == 200, f"Expected status 200, got {updated_response.status_code}. Response: {updated_response.text}"
        data = updated_response.json()
        power_state = data.get("PowerState")
        assert power_state in ("On", "PoweringOn"), f"PowerState should be On or PoweringOn after reset. Got: {power_state}. Response: {data}"
        logger.info("Power management test passed")
    except requests.RequestException as e:
        logger.error(f"Power management request failed: {e}")
        logger.error(f"Response body (if available): {e.response.text if e.response else 'No response object'}")
        pytest.fail(f"Power management request failed: {e}")
