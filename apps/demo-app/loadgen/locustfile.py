"""
Locust Load Generator for Multi-tenant OpenTelemetry Demo App

This Locust file generates load against the sender service endpoints.
"""

import os
import random
import logging
from locust import HttpUser, task, between
from locust.contrib.fasthttp import FastHttpUser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry instrumentation
# This must be imported before Locust starts to ensure instrumentation is active
try:
    import instrumentation  # This initializes OpenTelemetry
    SERVICE_NAME = instrumentation.SERVICE_NAME
    TENANT_ID = instrumentation.TENANT_ID
except ImportError:
    # Fallback if instrumentation module not available
    SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "loadgen-service")
    TENANT_ID = os.getenv("TENANT_ID", "default")


class DemoAppUser(FastHttpUser):
    """
    Locust user that simulates requests to the demo app sender service.
    """
    wait_time = between(0.5, 2.0)  # Wait between 0.5 and 2 seconds between requests
    
    def on_start(self):
        """Called when a simulated user starts"""
        # Health check to ensure service is available
        # Locust instrumentation will automatically create spans for HTTP requests
        self.client.get("/health", name="GET /health (startup)")
    
    @task(3)
    def send_message(self):
        """
        Main task: Send a message to the sender service.
        This is weighted 3x more than the health check.
        """
        request_id = f"loadgen-{random.randint(1000, 9999)}"
        payload = {
            "request_id": request_id,
            "message": f"Load test message {request_id}",
            "data": {
                "source": "locust-loadgen",
                "test": True,
                "random_value": random.randint(1, 100)
            }
        }
        
        try:
            with self.client.post(
                "/send",
                json=payload,
                catch_response=True,
                name="POST /send"
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 500:
                    # Simulated errors are expected, mark as success for load testing
                    logger.info(f"POST /send returned 500 (simulated error) for request_id={request_id}")
                    response.success()
                else:
                    error_msg = f"Unexpected status code: {response.status_code}"
                    logger.error(f"POST /send failed - {error_msg} for request_id={request_id}, status_code={response.status_code}")
                    response.failure(error_msg)
        except Exception as e:
            error_msg = f"POST /send exception: {type(e).__name__}: {str(e)}"
            logger.error(f"POST /send failed - {error_msg} for request_id={request_id}", exc_info=True)
            # Re-raise to let Locust handle it as a failure
            raise
    
    @task(1)
    def health_check(self):
        """Health check endpoint - lower weight"""
        self.client.get("/health", name="GET /health")
    
    @task(1)
    def metrics_endpoint(self):
        """Metrics endpoint - lower weight"""
        self.client.get("/metrics", name="GET /metrics")


class WebsiteUser(HttpUser):
    """
    Alternative user class using standard HttpUser (slower but more compatible).
    Use this if FastHttpUser causes issues.
    """
    wait_time = between(0.5, 2.0)
    
    def on_start(self):
        self.client.get("/health")
    
    @task(3)
    def send_message(self):
        request_id = f"loadgen-{random.randint(1000, 9999)}"
        payload = {
            "request_id": request_id,
            "message": f"Load test message {request_id}",
            "data": {
                "source": "locust-loadgen",
                "test": True
            }
        }
        try:
            response = self.client.post("/send", json=payload, name="POST /send")
            if response.status_code not in [200, 500]:
                logger.error(f"POST /send failed - status_code={response.status_code} for request_id={request_id}")
        except Exception as e:
            error_msg = f"POST /send exception: {type(e).__name__}: {str(e)}"
            logger.error(f"POST /send failed - {error_msg} for request_id={request_id}", exc_info=True)
            raise
    
    @task(1)
    def health_check(self):
        self.client.get("/health", name="GET /health")

