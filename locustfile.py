from locust import HttpUser, task, between, events
import requests # Import requests for on_start if needed for more control
import logging

logging.basicConfig(level=logging.INFO) # Ensure this is effective
logger = logging.getLogger(__name__)
# For more detailed locust specific logs, you might need to configure locust's own logger
# from locust.log import setup_logging
# setup_logging("INFO", None)


BMC_URL = "https://localhost:2443"
AUTH_URL = f"{BMC_URL}/redfish/v1/SessionService/Sessions"
CREDENTIALS = {"UserName": "root", "Password": "0penBmc"}
REQUEST_TIMEOUT = 60 # Increased timeout

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("Locust test started. Environment variables will be used for BMC connection.")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("Locust test stopped")

class OpenBMCUser(HttpUser):
    host = BMC_URL # This will be the base for self.client.get/post
    wait_time = between(1, 5)
    token = None # Class attribute to store token

    def on_start(self):
        """
        Called when a Locust User starts before any tasks are scheduled.
        Attempt to get a session token.
        """
        logger.info(f"OpenBMCUser instance starting. Attempting to create session at {AUTH_URL} with timeout {REQUEST_TIMEOUT}s.")
        try:
            # Using self.client which is a pre-configured requests.Session instance
            response = self.client.post(
                "/redfish/v1/SessionService/Sessions", # Relative to self.host
                json=CREDENTIALS,
                headers={"Content-Type": "application/json"},
                verify=False, # Important for self-signed certs
                timeout=REQUEST_TIMEOUT,
                name="Create Session (on_start)" # Name for Locust stats
            )
            
            logger.info(f"OpenBMCUser on_start: Session creation response status: {response.status_code}")
            if response.ok: # Check for 2xx status codes
                self.token = response.headers.get("X-Auth-Token")
                if self.token:
                    logger.info("OpenBMCUser on_start: Session token created successfully.")
                else:
                    logger.error("OpenBMCUser on_start: No X-Auth-Token found in response headers. Response: %s", response.text)
                    self.token = None # Ensure token is None if not found
            else:
                logger.error(f"OpenBMCUser on_start: Session creation failed with status {response.status_code}. Response: {response.text}")
                self.token = None # Ensure token is None on failure

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenBMCUser on_start: Error creating session: {type(e).__name__} - {e}")
            self.token = None # Ensure token is None on exception
        except Exception as e:
            logger.error(f"OpenBMCUser on_start: An unexpected error occurred during session creation: {type(e).__name__} - {e}")
            self.token = None


    @task(1) # Add weight if you have multiple tasks
    def get_system_info(self):
        if not self.token:
            logger.warning("OpenBMCUser: Skipping get_system_info task as no valid session token is available.")
            return

        logger.debug(f"OpenBMCUser: Attempting to get system info with token {self.token[:10]}...") # Log first 10 chars of token
        try:
            with self.client.get(
                "/redfish/v1/Systems/system", # Relative to self.host
                headers={"X-Auth-Token": self.token},
                verify=False,
                timeout=REQUEST_TIMEOUT,
                name="Get System Info", # Name for Locust stats
                catch_response=True # Allows us to handle failures gracefully
            ) as response:
                if response.ok:
                    logger.info(f"OpenBMCUser get_system_info: Success - Status {response.status_code}")
                    response.success() # Mark as success for Locust
                else:
                    logger.error(f"OpenBMCUser get_system_info: Failed - Status {response.status_code}, Response: {response.text}")
                    response.failure(f"Failed with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenBMCUser get_system_info: RequestException: {type(e).__name__} - {e}")
            # Locust automatically handles this as a failure if not caught and response.failure() called
        except Exception as e:
            logger.error(f"OpenBMCUser get_system_info: An unexpected error occurred: {type(e).__name__} - {e}")


# Keep PublicAPIUser for now to ensure basic Locust functionality is working
class PublicAPIUser(HttpUser):
    host = "https://jsonplaceholder.typicode.com" # Note: Different host
    wait_time = between(1, 5)

    @task
    def get_posts(self):
        self.client.get("/posts", name="Get Posts (PublicAPI)")

    @task
    def get_comments(self):
        self.client.get("/comments", name="Get Comments (PublicAPI)")
