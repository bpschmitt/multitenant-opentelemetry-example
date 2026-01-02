# Multi-tenant OpenTelemetry Example

A complete example demonstrating multi-tenant OpenTelemetry telemetry collection in Kubernetes using the OpenTelemetry Collector and a demo application.

This repository provides:
- **OpenTelemetry Collector configurations** for both deployment and daemonset modes
- **Multi-tenant demo application** with sender, receiver, and load generator services
- **Helm charts** for easy deployment and configuration
- **Complete instrumentation examples** showing traces, metrics, and logs

## 📁 Repository Structure

```
multitenant-opentelemetry-example/
├── deployment/              # OpenTelemetry Collector deployment mode config
│   └── values.yaml          # Helm values for deployment mode
├── daemonset/               # OpenTelemetry Collector daemonset mode config
│   └── values.yaml          # Helm values for daemonset mode
├── demo-app/                # Multi-tenant demo application
│   ├── sender/             # Sender service (FastAPI)
│   ├── receiver/           # Receiver service (FastAPI)
│   ├── loadgen/            # Locust-based load generator
│   └── helm/               # Helm chart for demo app
│       └── demo-app/
│           ├── templates/  # Kubernetes manifests
│           ├── values.yaml  # Default values
│           ├── values-tenant1.yaml  # Tenant 1 overrides
│           └── values-tenant2.yaml  # Tenant 2 overrides
├── INSTALL.md              # OpenTelemetry Collector installation guide
└── README.md              # This file
```

## 🚀 Quick Start

### 1. Install OpenTelemetry Collector

Choose either deployment or daemonset mode based on your needs:

**Deployment Mode** (recommended for centralized collection):
```bash
# See INSTALL.md for detailed instructions
helm install opentelemetry-collector open-telemetry/opentelemetry-collector \
  --namespace otel-collector \
  --create-namespace \
  --values deployment/values.yaml
```

**Daemonset Mode** (recommended for node-level metrics and logs):
```bash
helm install opentelemetry-collector open-telemetry/opentelemetry-collector \
  --namespace otel-collector \
  --create-namespace \
  --values daemonset/values.yaml
```

📖 **Full installation instructions**: See [INSTALL.md](INSTALL.md)

### 2. Build and Deploy Demo Application

```bash
cd demo-app

# Build Docker images (see demo-app/README.md for details)
make build

# Deploy tenant 1
helm upgrade --install demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1 \
  --create-namespace \
  -f ./helm/demo-app/values-tenant1.yaml

# Deploy tenant 2
helm upgrade --install demo-app-tenant2 ./helm/demo-app \
  --namespace tenant2 \
  --create-namespace \
  -f ./helm/demo-app/values-tenant2.yaml
```

📖 **Full demo app documentation**: See [demo-app/README.md](demo-app/README.md)

## 🎯 Features

### OpenTelemetry Collector

- **Deployment Mode**: Centralized collection, Kubernetes events, cluster metrics
- **Daemonset Mode**: Node-level metrics, host logs, kubelet metrics
- **Multi-tenant Support**: Routes telemetry by tenant ID
- **New Relic Integration**: Configured to export to New Relic OTLP endpoint
- **Resource Attributes**: Automatically enriches telemetry with Kubernetes metadata

### Demo Application

- **Sender Service**: Receives HTTP requests and forwards to receiver
- **Receiver Service**: Processes requests with simulated database operations
- **Load Generator**: Locust-based load testing (deployment or job mode)
- **Complete Instrumentation**: Traces, metrics, and logs with proper semantic conventions
- **Multi-tenant Ready**: Supports multiple tenants with separate namespaces
- **Configurable**: Error rates, latency, processing time via environment variables

## 📊 Telemetry Data

The demo application generates:

- **Traces**: Distributed traces showing request flow (sender → receiver → database)
- **Metrics**: 
  - `requests_total` - Total request count
  - `request_duration_seconds` - Request latency histogram
  - `errors_total` - Error count
  - `processing_time_seconds` - Processing time histogram
- **Logs**: Structured logs with trace correlation

All telemetry includes:
- `service.name` - Service identifier
- `tenant.id` - Tenant identifier for multi-tenant filtering
- `service.version` - Application version

## 🔧 Configuration

### OpenTelemetry Collector

Configuration files are in `deployment/values.yaml` and `daemonset/values.yaml`. Key settings:

- **OTLP Receivers**: Accept telemetry from applications
- **New Relic Exporter**: Sends telemetry to New Relic
- **Processors**: Resource detection, batch processing, tenant routing
- **Pipelines**: Configured for traces, metrics, and logs

### Demo Application

Configuration is managed via Helm values:

- **Global settings**: Image registry, tenant ID, OTLP endpoint
- **Service-specific**: Error rates, latency, resource limits
- **Environment variables**: Can be set globally or per-service

See `demo-app/helm/demo-app/values.yaml` for all available options.

## 🧪 Testing

### Generate Load

**Using Locust (Deployment Mode with Web UI):**
```bash
# Enable loadgen
helm upgrade demo-app-tenant1 ./demo-app/helm/demo-app \
  --namespace tenant1 \
  -f ./demo-app/helm/demo-app/values-tenant1.yaml \
  --set loadgen.enabled=true \
  --set loadgen.mode=deployment

# Port-forward to access UI
kubectl port-forward -n tenant1 svc/loadgen 8089:8089

# Open http://localhost:8089 in your browser
```

**Using Locust (Job Mode - Headless):**
```bash
helm upgrade demo-app-tenant1 ./demo-app/helm/demo-app \
  --namespace tenant1 \
  -f ./demo-app/helm/demo-app/values-tenant1.yaml \
  --set loadgen.enabled=true \
  --set loadgen.mode=job \
  --set loadgen.job.users=20 \
  --set loadgen.job.spawnRate=5 \
  --set loadgen.job.runTime=10m
```

### Manual Testing

```bash
# Port-forward to sender service
kubectl port-forward -n tenant1 svc/sender 8000:8000

# Send a test request
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"request_id": "test-123", "message": "Hello from tenant1"}'
```

## 📚 Documentation

- **[INSTALL.md](INSTALL.md)**: Complete OpenTelemetry Collector installation guide
- **[demo-app/README.md](demo-app/README.md)**: Demo application documentation
- **[demo-app/helm/demo-app/values.yaml](demo-app/helm/demo-app/values.yaml)**: Helm chart configuration reference

## 🔍 Troubleshooting

### Collector Not Receiving Telemetry

1. **Check collector pods are running:**
   ```bash
   kubectl get pods -n otel-collector
   ```

2. **Check collector logs:**
   ```bash
   kubectl logs -n otel-collector -l app.kubernetes.io/name=opentelemetry-collector
   ```

3. **Verify OTLP endpoint configuration:**
   - For deployment mode: Use service endpoint
   - For daemonset mode: Use node IP (configured via environment variables)

### Demo App Not Sending Telemetry

1. **Check application logs:**
   ```bash
   kubectl logs -n tenant1 deployment/sender
   kubectl logs -n tenant1 deployment/receiver
   ```

2. **Verify OTLP endpoint environment variable:**
   ```bash
   kubectl exec -n tenant1 deployment/sender -- env | grep OTLP
   ```

3. **Check service connectivity:**
   ```bash
   kubectl get svc -n tenant1
   ```

## 🛠️ Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x
- kubectl configured
- Docker (for building images)
- New Relic account (or modify exporter for your backend)

## 📝 License

This is an example repository for demonstration purposes.

## 🤝 Contributing

This is a demonstration repository. Feel free to use it as a reference for your own OpenTelemetry implementations.

## 🔗 Additional Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry Collector Helm Chart](https://github.com/open-telemetry/opentelemetry-helm-charts)
- [New Relic OTLP Documentation](https://docs.newrelic.com/docs/more-integrations/open-source-telemetry-integrations/opentelemetry/opentelemetry-setup/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
