"""
Sender Service - Multi-tenant OpenTelemetry Demo App

This service receives HTTP requests and forwards them to the receiver service,
generating distributed traces, metrics, and logs along the way.
"""

import os
import time
import asyncio
import logging
import random
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import httpx
import uvicorn
from opentelemetry import trace, metrics
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
# OpenTelemetry logging imports (commented out - using STDOUT only)
# from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
# from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
# from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
# from opentelemetry._logs import set_logger_provider

# Configuration from environment variables
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "sender-service")
TENANT_ID = os.getenv("TENANT_ID", "default")
RECEIVER_SERVICE_URL = os.getenv("RECEIVER_SERVICE_URL", "http://receiver-service:8000")

# OTLP endpoint configuration
# If OTEL_EXPORTER_OTLP_ENDPOINT is set and not empty, use it
# Otherwise, if NODE_IP is set, construct endpoint from node IP
# Otherwise, use default
OTLP_ENDPOINT_ENV = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
NODE_IP = os.getenv("NODE_IP", "")
OTLP_PORT = os.getenv("OTLP_PORT", "4317")

# Check if OTLP_ENDPOINT_ENV is set and not empty
# os.getenv returns None if not set, but we default to "", so check for non-empty string
if OTLP_ENDPOINT_ENV and OTLP_ENDPOINT_ENV.strip():
    OTLP_ENDPOINT = OTLP_ENDPOINT_ENV
elif NODE_IP and NODE_IP.strip():
    OTLP_ENDPOINT = f"http://{NODE_IP}:{OTLP_PORT}"
else:
    OTLP_ENDPOINT = "http://opentelemetry-collector.otel-collector.svc.cluster.local:4317"

ERROR_RATE = float(os.getenv("ERROR_RATE", "0.0"))  # 0.0 = no errors, 1.0 = 100% errors
LATENCY_MS = int(os.getenv("LATENCY_MS", "0"))  # Artificial latency in milliseconds

# Create resource with attributes
resource = Resource.create({
    "service.name": SERVICE_NAME,
    "tenant.id": TENANT_ID,
    "service.version": "1.0.0",
})

# Initialize OpenTelemetry
# Traces
trace_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(trace_provider)
trace_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT))
)
tracer = trace.get_tracer(__name__)

# Metrics
metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
metrics_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(metrics_provider)
meter = metrics.get_meter(__name__)

# Create HTTP server metrics following OpenTelemetry semantic conventions
http_server_request_duration = meter.create_histogram(
    "http.server.request.duration",
    description="Duration of HTTP server requests",
    unit="s"
)
http_server_active_requests = meter.create_up_down_counter(
    "http.server.active_requests",
    description="Number of active HTTP server requests",
    unit="{request}"
)
http_server_request_body_size = meter.create_histogram(
    "http.server.request.body.size",
    description="Size of HTTP request bodies",
    unit="By"
)
http_server_response_body_size = meter.create_histogram(
    "http.server.response.body.size",
    description="Size of HTTP response bodies",
    unit="By"
)

# Create HTTP client metrics following OpenTelemetry semantic conventions
http_client_request_duration = meter.create_histogram(
    "http.client.request.duration",
    description="Duration of HTTP client requests",
    unit="s"
)
http_client_active_requests = meter.create_up_down_counter(
    "http.client.active_requests",
    description="Number of active HTTP client requests",
    unit="{request}"
)
http_client_request_body_size = meter.create_histogram(
    "http.client.request.body.size",
    description="Size of HTTP client request bodies",
    unit="By"
)
http_client_response_body_size = meter.create_histogram(
    "http.client.response.body.size",
    description="Size of HTTP client response bodies",
    unit="By"
)

# OpenTelemetry logging setup (commented out - using STDOUT only)
# logger_provider = LoggerProvider(resource=resource)
# set_logger_provider(logger_provider)
# logger_provider.add_log_record_processor(
#     BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTLP_ENDPOINT))
# )

# Configure Python logging to use OpenTelemetry
# handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
# logging.basicConfig(level=logging.INFO, handlers=[handler])

# Configure standard Python logging to STDOUT
# Custom formatter that includes trace context when available
class TraceContextFormatter(logging.Formatter):
    def format(self, record):
        # LoggingInstrumentor adds otelTraceID and otelSpanID to the record
        trace_id = getattr(record, 'otelTraceID', None) or ''
        span_id = getattr(record, 'otelSpanID', None) or ''
        
        # Set as record attributes for structured logging
        record.trace_id = trace_id
        record.span_id = span_id
        
        # Include trace context in the log output
        if trace_id and span_id:
            record.trace_context = f"[trace_id={trace_id} span_id={span_id}]"
        else:
            record.trace_context = ""
        
        return super().format(record)

handler = logging.StreamHandler()
formatter = TraceContextFormatter(
    '%(asctime)s - %(name)s - %(levelname)s %(trace_context)s - %(message)s'
)
handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
logger = logging.getLogger(__name__)

# Instrument logging to automatically inject trace context
# Note: We use a custom formatter above, so set_logging_format is not needed
LoggingInstrumentor().instrument()

# Log OTLP endpoint configuration
logger.info(
    f"OTLP endpoint configured: {OTLP_ENDPOINT}",
    extra={
        "otlp.endpoint": OTLP_ENDPOINT,
        "k8s.node.ip": NODE_IP,
        "tenant.id": TENANT_ID,
        "service.name": SERVICE_NAME
    }
)

# Create FastAPI app
app = FastAPI(title="Sender Service", version="1.0.0")


# HTTP Server Metrics Middleware
class HTTPServerMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract server attributes
        server_address = request.url.hostname or SERVICE_NAME
        server_port = request.url.port or 8000
        url_scheme = request.url.scheme
        http_method = request.method
        http_route = request.url.path  # Route path (e.g., "/send", "/health", "/metrics")
        
        # Get request body size if available
        request_body_size = None
        if request.headers.get("content-length"):
            try:
                request_body_size = int(request.headers.get("content-length", 0))
            except ValueError:
                pass
        
        # Increment active requests counter
        http_server_active_requests.add(
            1,
            {
                "server.address": server_address,
                "server.port": server_port,
                "http.request.method": http_method,
                "url.scheme": url_scheme,
                "http.route": http_route,
            }
        )
        
        status_code = 500
        response_body_size = None
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Try to get response body size
            if hasattr(response, "body") and response.body:
                response_body_size = len(response.body)
            elif hasattr(response, "content") and response.content:
                response_body_size = len(response.content)
            
            return response
        except HTTPException as e:
            status_code = e.status_code
            raise
        except Exception as e:
            status_code = 500
            raise
        finally:
            # Decrement active requests counter
            http_server_active_requests.add(
                -1,
                {
                    "server.address": server_address,
                    "server.port": server_port,
                    "http.request.method": http_method,
                    "url.scheme": url_scheme,
                    "http.route": http_route,
                }
            )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record duration metric with required attributes
            attributes = {
                "http.request.method": http_method,
                "http.response.status_code": status_code,
                "server.address": server_address,
                "server.port": server_port,
                "url.scheme": url_scheme,
                "http.route": http_route,
            }
            
            http_server_request_duration.record(duration, attributes)
            
            # Record body size metrics if available
            if request_body_size is not None and request_body_size > 0:
                http_server_request_body_size.record(request_body_size, attributes)
            
            if response_body_size is not None and response_body_size > 0:
                http_server_response_body_size.record(response_body_size, attributes)


# Add middleware to app
app.add_middleware(HTTPServerMetricsMiddleware)

# Instrument FastAPI and HTTPX
# Configure FastAPI instrumentation to capture all routes including health checks
# Note: FastAPI instrumentation automatically instruments uvicorn as well
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="",  # Don't exclude any URLs - capture all endpoints
    server_request_hook=None,
    client_request_hook=None,
    tracer_provider=trace_provider
)
HTTPXClientInstrumentor().instrument(tracer_provider=trace_provider)

@app.get("/health")
async def health():
    """Health check endpoint"""
    # Get current span (created by FastAPI instrumentation)
    # FastAPI instrumentation already sets standard HTTP attributes
    # We only add custom application-specific attributes
    current_span = trace.get_current_span()
    if current_span:
        # Custom attributes (not part of semantic conventions but useful for filtering)
        current_span.set_attribute("app.endpoint.type", "health")
        current_span.set_attribute("app.tenant.id", TENANT_ID)
    return {"status": "healthy", "service": SERVICE_NAME, "tenant": TENANT_ID}


@app.post("/send")
async def send_message(data: Optional[dict] = None):
    """
    Main endpoint that receives requests and forwards them to the receiver service.
    Generates traces, metrics, and logs.
    """
    # Get current span (created by FastAPI instrumentation)
    # FastAPI instrumentation already sets standard HTTP attributes (http.method, http.route, etc.)
    current_span = trace.get_current_span()
    if current_span:
        # Custom application-specific attributes
        current_span.set_attribute("app.endpoint.type", "api")
        current_span.set_attribute("app.tenant.id", TENANT_ID)
    
    request_id = data.get("request_id", "unknown") if data else "unknown"
    
    logger.info(
        "Received request to send",
        extra={
            "request.id": request_id,
            "tenant.id": TENANT_ID,
            "service.name": SERVICE_NAME
        }
    )
    
    # Simulate artificial latency if configured
    if LATENCY_MS > 0:
        with tracer.start_as_current_span("artificial_latency", kind=trace.SpanKind.INTERNAL) as latency_span:
            latency_span.set_attribute("app.latency.ms", LATENCY_MS)
            await asyncio.sleep(LATENCY_MS / 1000.0)
    
    # Simulate errors if configured
    if random.random() < ERROR_RATE:
        if current_span:
            current_span.set_status(trace.Status(trace.StatusCode.ERROR, "Simulated error"))
            current_span.set_attribute("error.type", "simulated_error")
            current_span.set_attribute("error.message", "Simulated error for testing")
        logger.error(
            "Simulated error occurred",
            extra={
                "request.id": request_id,
                "tenant.id": TENANT_ID,
                "service.name": SERVICE_NAME
            }
        )
        raise HTTPException(status_code=500, detail="Simulated error")
    
    # Note: httpx instrumentation will automatically create HTTP client spans with proper semantic conventions
    # We create a wrapper span for business logic context
    with tracer.start_as_current_span("call_receiver", kind=trace.SpanKind.INTERNAL) as span:
        # Custom application attributes
        span.set_attribute("app.tenant.id", TENANT_ID)
        span.set_attribute("app.request.id", request_id)
        span.set_attribute("peer.service", "receiver-service")
        
        try:
            # Forward request to receiver service
            # httpx instrumentation will create HTTP client spans with proper semantic conventions:
            # - http.method, http.url, http.status_code, http.request_content_length, etc.
            
            # Extract client attributes from receiver URL
            from urllib.parse import urlparse
            receiver_url = urlparse(RECEIVER_SERVICE_URL)
            client_server_address = receiver_url.hostname or "receiver-service"
            client_server_port = receiver_url.port or 8000
            client_url_scheme = receiver_url.scheme or "http"
            client_method = "POST"
            client_route = "/process"  # Route being called on receiver service
            
            # Increment active client requests
            http_client_active_requests.add(
                1,
                {
                    "server.address": client_server_address,
                    "server.port": client_server_port,
                    "http.request.method": client_method,
                    "url.scheme": client_url_scheme,
                    "http.route": client_route,
                }
            )
            
            client_start_time = time.time()
            request_body_size = None
            response_body_size = None
            client_status_code = 500
            
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    payload = {
                        "request_id": request_id,
                        "tenant_id": TENANT_ID,
                        "sender": SERVICE_NAME,
                        "data": data or {}
                    }
                    
                    # Estimate request body size
                    request_body_size = len(json.dumps(payload).encode('utf-8'))
                    
                    response = await client.post(
                        f"{RECEIVER_SERVICE_URL}/process",
                        json=payload
                    )
                    client_status_code = response.status_code
                    
                    # Get response body size
                    if hasattr(response, "content"):
                        response_body_size = len(response.content)
                    
                    # Check status before parsing JSON to ensure receiver errors are properly handled
                    # raise_for_status() will raise HTTPStatusError (subclass of HTTPError) for non-2xx
                    # This ensures receiver errors (4xx, 5xx) are caught as HTTPError and converted to 502
                    response.raise_for_status()
                    
                    # Only parse JSON if status is OK (2xx)
                    # If JSON parsing fails, treat as receiver service error (502) not internal error (500)
                    try:
                        result = response.json()
                    except (json.JSONDecodeError, ValueError) as json_error:
                        # If we can't parse JSON from a successful response, treat as receiver error
                        # This should be rare but could happen with malformed responses
                        # We need to ensure this is caught as a receiver error (502) not internal error (500)
                        # Record the error on the span and log it, then raise HTTPException
                        # The HTTPException will be caught by the outer Exception handler, but we'll
                        # handle it specially to return 502 instead of 500
                        error_msg = f"Invalid JSON response from receiver: {str(json_error)}"
                        span.record_exception(json_error)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
                        span.set_attribute("error.type", "json_decode_error")
                        span.set_attribute("error.message", error_msg)
                        logger.error(
                            "Failed to parse JSON response from receiver",
                            extra={
                                "request.id": request_id,
                                "tenant.id": TENANT_ID,
                                "error.message": error_msg
                            },
                            exc_info=True
                        )
                        # Raise HTTPException with 502 to indicate receiver service error
                        raise HTTPException(status_code=502, detail=error_msg)
            finally:
                # Decrement active client requests
                http_client_active_requests.add(
                    -1,
                    {
                        "server.address": client_server_address,
                        "server.port": client_server_port,
                        "http.request.method": client_method,
                        "url.scheme": client_url_scheme,
                        "http.route": client_route,
                    }
                )
                
                # Calculate client duration
                client_duration = time.time() - client_start_time
                
                # Record client duration metric
                client_attributes = {
                    "http.request.method": client_method,
                    "http.response.status_code": client_status_code,
                    "server.address": client_server_address,
                    "server.port": client_server_port,
                    "url.scheme": client_url_scheme,
                    "http.route": client_route,
                }
                
                http_client_request_duration.record(client_duration, client_attributes)
                
                # Record body size metrics if available
                if request_body_size is not None and request_body_size > 0:
                    http_client_request_body_size.record(request_body_size, client_attributes)
                
                if response_body_size is not None and response_body_size > 0:
                    http_client_response_body_size.record(response_body_size, client_attributes)
            
            # Success path - only reached if no exceptions were raised
            # Custom attributes for business logic span
            span.set_attribute("app.receiver.response.status", response.status_code)
            span.set_status(trace.Status(trace.StatusCode.OK))
            logger.info(
                "Successfully forwarded request to receiver",
                extra={
                    "request.id": request_id,
                    "tenant.id": TENANT_ID,
                    "http.status_code": response.status_code
                }
            )
            
            return {
                "status": "success",
                "sender": SERVICE_NAME,
                "tenant": TENANT_ID,
                "receiver_response": result
            }
                
        except httpx.HTTPError as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Exception recording automatically sets error.type, error.message, error.stack
            logger.error(
                "Failed to forward request to receiver",
                extra={
                    "request.id": request_id,
                    "tenant.id": TENANT_ID,
                    "error.message": str(e)
                },
                exc_info=True
            )
            raise HTTPException(status_code=502, detail=f"Receiver service error: {str(e)}")
        except HTTPException:
            # Re-raise HTTPException so FastAPI handles it properly
            # This allows JSON parsing errors to be returned as 502 instead of 500
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Exception recording automatically sets error.type, error.message, error.stack
            logger.error(
                "Unexpected error",
                extra={
                    "request.id": request_id,
                    "tenant.id": TENANT_ID,
                    "error.message": str(e)
                },
                exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint (basic implementation)"""
    # Get current span (created by FastAPI instrumentation)
    # FastAPI instrumentation already sets standard HTTP attributes
    current_span = trace.get_current_span()
    if current_span:
        # Custom application-specific attributes
        current_span.set_attribute("app.endpoint.type", "metrics")
        current_span.set_attribute("app.tenant.id", TENANT_ID)
    return JSONResponse(
        content={
            "message": "Use OpenTelemetry Collector to scrape OTLP metrics",
            "service": SERVICE_NAME,
            "tenant": TENANT_ID
        }
    )


if __name__ == "__main__":
    # Disable uvicorn access logs - HTTP request details are already captured
    # in OpenTelemetry traces via FastAPI instrumentation
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False, log_config=None)

