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
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider

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

# Create custom metrics
requests_total = meter.create_counter(
    "requests_total",
    description="Total number of requests",
    unit="1"
)
request_duration = meter.create_histogram(
    "request_duration_seconds",
    description="Request duration in seconds",
    unit="s"
)
errors_total = meter.create_counter(
    "errors_total",
    description="Total number of errors",
    unit="1"
)

# Logs
logger_provider = LoggerProvider(resource=resource)
set_logger_provider(logger_provider)
logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTLP_ENDPOINT))
)

# Configure Python logging to use OpenTelemetry
handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# Log OTLP endpoint configuration
logger.info(
    f"OTLP endpoint configured: {OTLP_ENDPOINT}",
    extra={
        "otlp_endpoint": OTLP_ENDPOINT,
        "node_ip": NODE_IP,
        "tenant_id": TENANT_ID,
        "service": SERVICE_NAME
    }
)

# Create FastAPI app
app = FastAPI(title="Sender Service", version="1.0.0")

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

# Get current span context for logging
def get_trace_context():
    """Get current trace context for logging"""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        trace_id = format(span.get_span_context().trace_id, '032x')
        span_id = format(span.get_span_context().span_id, '016x')
        return {"trace_id": trace_id, "span_id": span_id}
    return {}


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
    
    start_time = time.time()
    request_id = data.get("request_id", "unknown") if data else "unknown"
    
    # Add trace context to logs
    trace_context = get_trace_context()
    logger.info(
        "Received request to send",
        extra={
            "request_id": request_id,
            "tenant_id": TENANT_ID,
            "service": SERVICE_NAME,
            **trace_context
        }
    )
    
    # Simulate artificial latency if configured
    if LATENCY_MS > 0:
        with tracer.start_as_current_span("artificial_latency", kind=trace.SpanKind.INTERNAL) as latency_span:
            latency_span.set_attribute("app.latency.ms", LATENCY_MS)
            await asyncio.sleep(LATENCY_MS / 1000.0)
    
    # Simulate errors if configured
    if random.random() < ERROR_RATE:
        errors_total.add(1, {"tenant_id": TENANT_ID, "service": SERVICE_NAME, "error_type": "simulated"})
        if current_span:
            current_span.set_status(trace.Status(trace.StatusCode.ERROR, "Simulated error"))
            current_span.set_attribute("error.type", "simulated_error")
            current_span.set_attribute("error.message", "Simulated error for testing")
        logger.error(
            "Simulated error occurred",
            extra={
                "request_id": request_id,
                "tenant_id": TENANT_ID,
                "service": SERVICE_NAME,
                **trace_context
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
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "request_id": request_id,
                    "tenant_id": TENANT_ID,
                    "sender": SERVICE_NAME,
                    "data": data or {}
                }
                response = await client.post(
                    f"{RECEIVER_SERVICE_URL}/process",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                # Custom attributes for business logic span
                span.set_attribute("app.receiver.response.status", response.status_code)
                span.set_status(trace.Status(trace.StatusCode.OK))
                logger.info(
                    "Successfully forwarded request to receiver",
                    extra={
                        "request_id": request_id,
                        "tenant_id": TENANT_ID,
                        "receiver_status": response.status_code,
                        **trace_context
                    }
                )
                
                duration = time.time() - start_time
                requests_total.add(1, {"tenant_id": TENANT_ID, "service": SERVICE_NAME, "status": "success"})
                request_duration.record(duration, {"tenant_id": TENANT_ID, "service": SERVICE_NAME})
                
                return {
                    "status": "success",
                    "sender": SERVICE_NAME,
                    "tenant": TENANT_ID,
                    "receiver_response": result,
                    "duration_seconds": duration
                }
                
        except httpx.HTTPError as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Exception recording automatically sets error.type, error.message, error.stack
            duration = time.time() - start_time
            errors_total.add(1, {"tenant_id": TENANT_ID, "service": SERVICE_NAME, "error_type": "http_error"})
            logger.error(
                "Failed to forward request to receiver",
                extra={
                    "request_id": request_id,
                    "tenant_id": TENANT_ID,
                    "error": str(e),
                    **trace_context
                },
                exc_info=True
            )
            raise HTTPException(status_code=502, detail=f"Receiver service error: {str(e)}")
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Exception recording automatically sets error.type, error.message, error.stack
            duration = time.time() - start_time
            errors_total.add(1, {"tenant_id": TENANT_ID, "service": SERVICE_NAME, "error_type": "unknown"})
            logger.error(
                "Unexpected error",
                extra={
                    "request_id": request_id,
                    "tenant_id": TENANT_ID,
                    "error": str(e),
                    **trace_context
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
    import uvicorn
    import asyncio
    uvicorn.run(app, host="0.0.0.0", port=8000)

