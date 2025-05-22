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
            logger.info(f"OpenBMCUser: Attempting session creation to {AUTH_URL}")
            response = self.client.post(
                "/redfish/v1/SessionService/Sessions",
                json=CREDENTIALS,
                headers={"Content-Type": "application/json"},
                verify=False,
                name="Create Session"
            )
            if response.status_code not in (200, 201):
                logger.error(f"OpenBMCUser: Session creation failed: {response.status_code}, Response text: {response.text}")
                self.token = None
                return
            self.token = response.headers.get("X-Auth-Token")
            if not self.token:
                logger.error("OpenBMCUser: No X-Auth-Token found in response headers")
            else:
                logger.info("OpenBMCUser: Session token created successfully")
        except Exception as e:
            logger.error(f"OpenBMCUser: Error creating session: {e}")
            self.token = None

    @task
    def get_system_info(self):
        if not hasattr(self, "token") or not self.token:
            logger.warning("OpenBMCUser: Skipping task get_system_info - No valid session token")
            return
        
        logger.info("OpenBMCUser: Attempting to get system info")
        try:
            with self.client.get(
                "/redfish/v1/Systems/system",
                headers={"X-Auth-Token": self.token},
                verify=False,
                name="Get System Info",
                catch_response=True
            ) as response:
                if response.ok:
                    logger.info(f"OpenBMCUser: Get System Info successful: {response.status_code}")
                    response.success()
                else:
                    logger.error(f"OpenBMCUser: Get System Info failed: {response.status_code}, {response.text}")
                    response.failure(f"Status code {response.status_code}")
        except Exception as e:
            logger.error(f"OpenBMCUser: Error during Get System Info: {e}")
            if hasattr(self, 'environment'):
                 self.environment.events.request.fire(
                    request_type="GET",
                    name="Get System Info",
                    response_time=0, 
                    exception=e,
                    response_length=0
                )
            
class PublicAPIUser(HttpUser):
    host = "Public APIs" 
    wait_time = between(1, 5)

    @task
    def get_posts(self):
        logger.info("PublicAPIUser: Attempting to get posts from jsonplaceholder...")
        try:
            with self.client.get(
                "https://jsonplaceholder.typicode.com/posts",
                name="Get Posts",
                timeout=10,
                catch_response=True
            ) as response:
                if response.ok:
                    logger.info(f"PublicAPIUser: Get Posts successful: {response.status_code}")
                    response.success()
                else:
                    logger.error(f"PublicAPIUser: Get Posts failed: {response.status_code}, Response text: {response.text}")
                    response.failure(f"Status code {response.status_code}")
        except Exception as e:
            logger.error(f"PublicAPIUser: Error during Get Posts: {e}")
            if hasattr(self, 'environment'):
                 self.environment.events.request.fire(
                    request_type="GET",
                    name="Get Posts",
                    response_time=0,
                    exception=e,
                    response_length=0
                )


    @task
    def get_weather(self):
        logger.info("PublicAPIUser: Attempting to get weather from wttr.in...")
        try:
            with self.client.get(
                "https://wttr.in/Novosibirsk?format=j1",
                name="Get Weather",
                timeout=10, 
                catch_response=True
            ) as response:
                if response.ok:
                    logger.info(f"PublicAPIUser: Get Weather successful: {response.status_code}")
                    response.success()
                else:
                    logger.error(f"PublicAPIUser: Get Weather failed: {response.status_code}, Response text: {response.text}")
                    response.failure(f"Status code {response.status_code}")
        except Exception as e:
            logger.error(f"PublicAPIUser: Error during Get Weather: {e}")
            if hasattr(self, 'environment'):
                self.environment.events.request.fire(
                    request_type="GET",
                    name="Get Weather",
                    response_time=0,
                    exception=e,
                    response_length=0
                )
