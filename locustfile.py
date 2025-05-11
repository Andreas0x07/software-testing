from locust import HttpUser, task, between, events
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BMC_URL = "https://localhost:2443"
AUTH_URL = f"{BMC_URL}/redfish/v1/SessionService/Sessions"
CREDENTIALS = {"UserName": "root", "Password": "0penBmc"}

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("Test started")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("Test stopped")

class OpenBMCUser(HttpUser):
    host = BMC_URL
    wait_time = between(1, 5)

    def on_start(self):
        try:
            response = self.client.post(
                "/redfish/v1/SessionService/Sessions",
                json=CREDENTIALS,
                headers={"Content-Type": "application/json"},
                verify=False,
                name="Create Session"
            )
            if response.status_code not in (200, 201):
                logger.error(f"Session creation failed: {response.status_code}, {response.text}")
                return
            self.token = response.headers.get("X-Auth-Token")
            if not self.token:
                logger.error("No X-Auth-Token found in response headers")
            else:
                logger.info("Session token created successfully")
        except Exception as e:
            logger.error(f"Error creating session: {e}")

    @task
    def get_system_info(self):
        if not hasattr(self, "token") or not self.token:
            logger.warning("Skipping task: No valid session token")
            return
        self.client.get(
            "/redfish/v1/Systems/system",
            headers={"X-Auth-Token": self.token},
            verify=False,
            name="Get System Info"
        )
        
class PublicAPIUser(HttpUser):
    host = "Public APIs"
    wait_time = between(1, 5)

    @task
    def get_posts(self):
        self.client.get(
            "https://jsonplaceholder.typicode.com/posts",
            name="Get Posts"
        )

    @task
    def get_weather(self):
        self.client.get(
            "https://wttr.in/Novosibirsk?format=j1",
            name="Get Weather"
        )
