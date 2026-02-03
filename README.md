# Multi-tenant OpenTelemetry Example

A complete example demonstrating multi-tenant OpenTelemetry telemetry collection in Kubernetes using the OpenTelemetry Collector and a demo application.

This repository provides:
- **OpenTelemetry Collector configurations** for both deployment and daemonset modes
- **OpenTelemetry Operator support** for CRD-based collector management and auto-instrumentation
- **Multi-tenant demo application** with sender, receiver, and load generator services
- **Helm charts** for easy deployment and configuration
- **Complete instrumentation examples** showing traces, metrics, and logs

## 📁 Repository Structure

```
multitenant-opentelemetry-example/
├── apps/                      # Application deployments
│   └── demo-app/             # Multi-tenant demo application
│       ├── sender/           # Sender service (FastAPI)
│       ├── receiver/         # Receiver service (FastAPI)
│       ├── loadgen/          # Locust-based load generator
│       ├── helm/             # Helm chart for demo app
│       ├── Makefile          # Build scripts
│       └── README.md         # Demo app documentation
├── deployments/              # OpenTelemetry Collector deployments
│   ├── otel-collector/       # Helm-based collector deployments
│   │   └── README.md         # Helm deployment instructions
│   └── otel-operator/        # CRD-based collector deployments
│       └── README.md         # Operator deployment instructions
├── CONFIGURATION.md          # Detailed collector configuration documentation
└── README.md                 # This file
```

## 🛠️ Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x
- kubectl configured
- Docker (for building images)
- New Relic account with license keys:
  - Default license key (for non-tenant namespaces)
  - Tenant 1 license key (optional, for tenant1-demo namespace)
  - Tenant 2 license key (optional, for tenant2-demo namespace)
- Docker registry access (for pushing demo app images)
- **OpenShift users**: May need to configure Security Context Constraints (SCC) for the operator

## 🚀 Quick Start

### 1. Choose Deployment Method

This repository supports two deployment methods for OpenTelemetry Collectors:

- **OpenTelemetry Operator (Recommended)**: CRD-based management with automatic instrumentation support
  - See [deployments/otel-operator/README.md](deployments/otel-operator/README.md) for detailed instructions

- **Helm Charts (Direct)**: Direct Helm-based installation without operator
  - See [deployments/otel-collector/README.md](deployments/otel-collector/README.md) for detailed instructions

### 2. Deploy Demo Application

```bash
cd apps/demo-app

# Build Docker images (see apps/demo-app/README.md for details)
# Update imageRegistry in values-tenant1.yaml and values-tenant2.yaml first
make build REGISTRY=ghcr.io/myorg # update with your own registry

# Deploy tenant 1
helm upgrade --install demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --create-namespace \
  -f ./helm/demo-app/values-tenant1.yaml

# Deploy tenant 2
helm upgrade --install demo-app-tenant2 ./helm/demo-app \
  --namespace tenant2-demo \
  --create-namespace \
  -f ./helm/demo-app/values-tenant2.yaml
```

**Note**: The demo app is configured to use node-local endpoints by default (for daemonset mode). If using deployment mode only, update the values files to set `useNodeLocalEndpoint: false` and configure `otlpEndpoint`.

📖 **Full demo app documentation**: See [apps/demo-app/README.md](apps/demo-app/README.md)

## 🏗️ Architecture

### Multi-Tenant Routing

This example demonstrates a multi-tenant OpenTelemetry collection architecture:

1. **Application Layer**: Demo applications deployed in separate Kubernetes namespaces (`tenant1-demo`, `tenant2-demo`)
2. **Collection Layer**: 
   - **Daemonset Collectors**: Collect node-level metrics, logs, and kubelet metrics from each node
   - **Deployment Gateway**: Centralized collector that receives telemetry from daemonset collectors and applications
3. **Routing Layer**: OpenTelemetry routing connectors route telemetry based on `k8s.namespace.name` attribute:
   - `tenant1-demo` namespace → `otlphttp/tenant1` exporter (uses `NEW_RELIC_LICENSE_KEY_TENANT1`)
   - `tenant2-demo` namespace → `otlphttp/tenant2` exporter (uses `NEW_RELIC_LICENSE_KEY_TENANT2`)
   - Other namespaces → `otlphttp/newrelic` exporter (uses `NEW_RELIC_LICENSE_KEY`)
4. **Export Layer**: Each tenant's telemetry is exported to New Relic using tenant-specific license keys

### Data Flow

```
Application Pods (tenant1-demo/tenant2-demo)
    ↓ (OTLP)
Daemonset Collectors (per node)
    ↓ (OTLP HTTP)
Deployment Gateway Collector
    ↓ (Routing Connectors)
Tenant-Specific Exporters
    ↓ (OTLP HTTP)
New Relic (per-tenant accounts)
```

### Deployment Modes

- **Deployment Mode Only**: Applications send directly to deployment collector, which handles routing
- **Hybrid Mode** (Recommended): Daemonset collectors forward to deployment gateway for centralized routing and node-level collection

### Key Features

- **Multi-tenant Support**: Routes telemetry by namespace using routing connectors
- **New Relic Integration**: Configured to export to New Relic OTLP endpoint with per-tenant license keys
- **Resource Attributes**: Automatically enriches telemetry with Kubernetes metadata
- **CRD-based Management**: Uses OpenTelemetry Operator for declarative collector configuration
- **Complete Instrumentation**: Demo app includes traces, metrics, and logs with proper semantic conventions

## 📊 Telemetry Data

The demo application generates:

- **Traces**: Distributed traces showing request flow (sender → receiver → database)
- **Metrics**: Following HTTP semantic conventions
  - `http.server.request.duration` - Duration of HTTP server requests (histogram, seconds)
  - `http.server.active_requests` - Number of active HTTP server requests (up_down_counter)
  - `http.server.request.body.size` - Size of HTTP request bodies (histogram, bytes)
  - `http.server.response.body.size` - Size of HTTP response bodies (histogram, bytes)
  - `http.client.request.duration` - Duration of HTTP client requests (histogram, seconds) - Sender only
  - `http.client.active_requests` - Number of active HTTP client requests (up_down_counter) - Sender only
  - `http.client.request.body.size` - Size of HTTP client request bodies (histogram, bytes) - Sender only
  - `http.client.response.body.size` - Size of HTTP client response bodies (histogram, bytes) - Sender only
- **Logs**: Structured logs with trace correlation

All telemetry includes:
- `service.name` - Service identifier
- `tenant.id` - Tenant identifier for multi-tenant filtering
- `service.version` - Application version
- `k8s.namespace.name` - Kubernetes namespace (used for routing)
- `k8s.pod.name` - Kubernetes pod name
- `k8s.pod.ip` - Kubernetes pod IP address

## 🧪 Testing

### Manual Testing

```bash
# Port-forward to sender service
kubectl port-forward -n tenant1-demo svc/sender 8000:8000

# Send a test request
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"request_id": "test-123", "message": "Hello from tenant1"}'
```

### Load Testing

The demo app includes a Locust-based load generator. See [apps/demo-app/README.md](apps/demo-app/README.md) for details on running load tests.

## 📚 Documentation

- **[CONFIGURATION.md](CONFIGURATION.md)**: Detailed OpenTelemetry Collector configuration documentation
- **[apps/demo-app/README.md](apps/demo-app/README.md)**: Demo application documentation and usage guide
- **[deployments/otel-operator/README.md](deployments/otel-operator/README.md)**: OpenTelemetry Operator deployment instructions
- **[deployments/otel-collector/README.md](deployments/otel-collector/README.md)**: Helm-based collector deployment instructions

## 🔍 Troubleshooting

### Collector Not Receiving Telemetry

1. **Check collector pods are running:**
   ```bash
   kubectl get pods -n observability
   ```

2. **Check collector logs:**
   ```bash
   kubectl logs -n observability -l app.kubernetes.io/name=opentelemetry-collector
   ```

3. **Verify OTLP endpoint configuration:**
   - For deployment mode: Use service endpoint `opentelemetry-collector-deployment-collector.observability.svc.cluster.local:4317`
   - For daemonset mode: Use node IP (configured automatically via `status.hostIP`)

4. **Check routing configuration:**
   - Review collector config in [CONFIGURATION.md](CONFIGURATION.md)
   - See deployment-specific troubleshooting in respective README files

### Demo App Not Sending Telemetry

1. **Check application logs:**
   ```bash
   kubectl logs -n tenant1-demo deployment/sender
   kubectl logs -n tenant1-demo deployment/receiver
   ```

2. **Verify OTLP endpoint environment variable:**
   ```bash
   kubectl exec -n tenant1-demo deployment/sender -- env | grep OTLP
   ```

3. **Check service connectivity:**
   ```bash
   kubectl get svc -n tenant1-demo
   ```

For more detailed troubleshooting, see the deployment-specific README files:
- [deployments/otel-operator/README.md](deployments/otel-operator/README.md)
- [deployments/otel-collector/README.md](deployments/otel-collector/README.md)

## 📝 License

This is an example repository for demonstration purposes.

## 🤝 Contributing

This is a demonstration repository. Feel free to use it as a reference for your own OpenTelemetry implementations.

## 🔗 Additional Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry Collector Helm Chart](https://github.com/open-telemetry/opentelemetry-helm-charts)
- [OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator)
- [OpenTelemetry Operator Helm Chart](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-operator)
- [New Relic OTLP Documentation](https://docs.newrelic.com/docs/more-integrations/open-source-telemetry-integrations/opentelemetry/opentelemetry-setup/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
