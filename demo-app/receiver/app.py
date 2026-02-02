"""
Receiver Service - Multi-tenant OpenTelemetry Demo App

This service receives requests from the sender service and processes them,
generating distributed traces, metrics, and logs.
"""

import os
import time
import asyncio
import logging
import random
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import uvicorn
from opentelemetry import trace, metrics
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
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
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "receiver-service")
TENANT_ID = os.getenv("TENANT_ID", "default")

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
PROCESSING_TIME_MS = int(os.getenv("PROCESSING_TIME_MS", "100"))  # Simulated processing time

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
app = FastAPI(title="Receiver Service", version="1.0.0")


# HTTP Server Metrics Middleware
class HTTPServerMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract server attributes
        server_address = request.url.hostname or SERVICE_NAME
        server_port = request.url.port or 8000
        url_scheme = request.url.scheme
        http_method = request.method
        http_route = request.url.path  # Route path (e.g., "/process", "/health", "/metrics")
        
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

# Instrument FastAPI
# Configure FastAPI instrumentation to capture all routes including health checks
# Note: FastAPI instrumentation automatically instruments uvicorn as well
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="",  # Don't exclude any URLs - capture all endpoints
    server_request_hook=None,
    client_request_hook=None,
    tracer_provider=trace_provider
)

@app.get("/health")
async def health():
    """Health check endpoint"""
    # Get current span (created by FastAPI instrumentation)
    # FastAPI instrumentation already sets standard HTTP attributes
    current_span = trace.get_current_span()
    if current_span:
        # Custom application-specific attributes
        current_span.set_attribute("app.endpoint.type", "health")
        current_span.set_attribute("app.tenant.id", TENANT_ID)
    return {"status": "healthy", "service": SERVICE_NAME, "tenant": TENANT_ID}


async def simulate_database_call(duration_ms: int):
    """Simulate a database call with a child span"""
    with tracer.start_as_current_span("database_query", kind=trace.SpanKind.CLIENT) as span:
        # Database semantic conventions
        span.set_attribute("db.system", "simulated")
        span.set_attribute("db.operation", "select")
        span.set_attribute("db.name", "demo_db")
        # Custom application attributes
        span.set_attribute("app.tenant.id", TENANT_ID)
        
        # Simulate database processing time
        await asyncio.sleep(duration_ms / 1000.0)
        
        # Simulate database result
        result = {"records": random.randint(1, 10), "status": "success"}
        # Use db.rows_affected for number of records returned (if applicable)
        # For count, we use a custom attribute since there's no standard for this
        span.set_attribute("app.db.records.count", result["records"])
        
        logger.debug(
            "Database query completed",
            extra={
                "tenant.id": TENANT_ID,
                "db.records.count": result["records"]
            }
        )
        
        return result


@app.post("/process")
async def process_request(data: dict):
    """
    Main endpoint that processes requests from the sender service.
    Generates traces, metrics, and logs with simulated database operations.
    """
    # Get current span (created by FastAPI instrumentation)
    # FastAPI instrumentation already sets standard HTTP attributes (http.method, http.route, etc.)
    current_span = trace.get_current_span()
    if current_span:
        # Custom application-specific attributes
        current_span.set_attribute("app.endpoint.type", "api")
    
    start_time = time.time()
    request_id = data.get("request_id", "unknown")
    sender = data.get("sender", "unknown")
    tenant_id = data.get("tenant_id", TENANT_ID)
    
    if current_span:
        current_span.set_attribute("app.tenant.id", tenant_id)
        current_span.set_attribute("app.request.id", request_id)
        current_span.set_attribute("app.sender.service", sender)
    
    logger.info(
        "Received request for processing",
        extra={
            "request.id": request_id,
            "sender.service": sender,
            "tenant.id": tenant_id,
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
            "Simulated error occurred during processing",
            extra={
                "request.id": request_id,
                "tenant.id": tenant_id,
                "service.name": SERVICE_NAME
            }
        )
        raise HTTPException(status_code=500, detail="Simulated processing error")
    
    try:
        # Simulate processing with a child span (internal span)
        with tracer.start_as_current_span("process_data", kind=trace.SpanKind.INTERNAL) as span:
            # Custom application attributes
            span.set_attribute("app.request.id", request_id)
            span.set_attribute("app.tenant.id", tenant_id)
            span.set_attribute("app.sender.service", sender)
            
            # Simulate database call (creates child span)
            db_result = await simulate_database_call(PROCESSING_TIME_MS)
            
            # Additional processing simulation
            await asyncio.sleep(0.01)  # 10ms additional processing
            
            processing_duration = time.time() - start_time
            
            result = {
                "status": "processed",
                "request_id": request_id,
                "tenant_id": tenant_id,
                "sender": sender,
                "receiver": SERVICE_NAME,
                "database_result": db_result,
                "processing_time_seconds": processing_duration
            }
            
            # Custom application attributes
            span.set_attribute("app.processing.success", True)
            span.set_attribute("app.processing.duration_seconds", processing_duration)
            span.set_status(trace.Status(trace.StatusCode.OK))
            
            # Update server span with success status
            # FastAPI instrumentation already sets http.status_code automatically
            if current_span:
                current_span.set_status(trace.Status(trace.StatusCode.OK))
            
            logger.info(
                "Request processed successfully",
                extra={
                    "request.id": request_id,
                    "tenant.id": tenant_id,
                }
            )
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        span = trace.get_current_span()
        if span:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Exception recording automatically sets error.type, error.message, error.stack
        
        logger.error(
            "Unexpected error during processing",
            extra={
                "request.id": request_id,
                "tenant.id": tenant_id,
                "error.message": str(e)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


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

