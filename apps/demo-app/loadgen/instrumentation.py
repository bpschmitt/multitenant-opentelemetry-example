"""
OpenTelemetry instrumentation setup for Locust load generator
"""

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# Configuration from environment variables
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "loadgen-service")
TENANT_ID = os.getenv("TENANT_ID", "default")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector.otel-collector.svc.cluster.local:4317")

# Get Kubernetes metadata
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", os.getenv("MY_POD_NAMESPACE", "default"))
K8S_POD_NAME = os.getenv("K8S_POD_NAME", os.getenv("MY_POD_NAME", "unknown"))

# Create resource with attributes
resource = Resource.create({
    "service.name": SERVICE_NAME,
    "tenant.id": TENANT_ID,
    "k8s.namespace": K8S_NAMESPACE,
    "k8s.pod.name": K8S_POD_NAME,
    "service.version": "1.0.0",
})

# Initialize OpenTelemetry
# Traces
trace_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(trace_provider)
trace_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT))
)

# Metrics
metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
metrics_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(metrics_provider)

# Instrument HTTP clients used by Locust
# FastHttpUser uses httpx, HttpUser uses requests
# This will automatically instrument HTTP requests made by Locust
try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    HTTPXClientInstrumentor().instrument(tracer_provider=trace_provider)
except ImportError:
    print("Warning: opentelemetry-instrumentation-httpx not available.")

try:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    RequestsInstrumentor().instrument(tracer_provider=trace_provider)
except ImportError:
    print("Warning: opentelemetry-instrumentation-requests not available.")

