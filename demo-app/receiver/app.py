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
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
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
processing_time = meter.create_histogram(
    "processing_time_seconds",
    description="Processing time in seconds",
    unit="s"
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
app = FastAPI(title="Receiver Service", version="1.0.0")

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
                "tenant_id": TENANT_ID,
                "records": result["records"],
                **get_trace_context()
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
    
    # Add trace context to logs
    trace_context = get_trace_context()
    logger.info(
        "Received request for processing",
        extra={
            "request_id": request_id,
            "sender": sender,
            "tenant_id": tenant_id,
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
        errors_total.add(1, {"tenant_id": tenant_id, "service": SERVICE_NAME, "error_type": "simulated"})
        if current_span:
            current_span.set_status(trace.Status(trace.StatusCode.ERROR, "Simulated error"))
            current_span.set_attribute("error.type", "simulated_error")
            current_span.set_attribute("error.message", "Simulated error for testing")
        logger.error(
            "Simulated error occurred during processing",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "service": SERVICE_NAME,
                **trace_context
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
            processing_time.record(processing_duration, {"tenant_id": tenant_id, "service": SERVICE_NAME})
            
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
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "processing_time": processing_duration,
                    **trace_context
                }
            )
            
            total_duration = time.time() - start_time
            requests_total.add(1, {"tenant_id": tenant_id, "service": SERVICE_NAME, "status": "success"})
            request_duration.record(total_duration, {"tenant_id": tenant_id, "service": SERVICE_NAME})
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        span = trace.get_current_span()
        if span:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Exception recording automatically sets error.type, error.message, error.stack
        
        duration = time.time() - start_time
        errors_total.add(1, {"tenant_id": tenant_id, "service": SERVICE_NAME, "error_type": "unknown"})
        logger.error(
            "Unexpected error during processing",
            extra={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "error": str(e),
                **trace_context
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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

