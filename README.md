# Multi-tenant OpenTelemetry Example

A complete example demonstrating multi-tenant OpenTelemetry telemetry collection in Kubernetes using the OpenTelemetry Collector and a demo application.

This repository provides:
- **OpenTelemetry Collector configurations** for both deployment and daemonset modes
- **OpenTelemetry Operator support** for CRD-based collector management and auto-instrumentation
- **Multi-tenant demo application** with sender, receiver, and load generator services
- **Helm charts** for easy deployment and configuration
- **Complete instrumentation examples** showing traces, metrics, and logs

## 🛠️ Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x
- kubectl configured
- Docker (for building images)
- New Relic account with license keys:
  - Default license key (for non-tenant namespaces)
  - Tenant 1 license key (optional, for tenant1 namespace)
  - Tenant 2 license key (optional, for tenant2 namespace)
- Docker registry access (for pushing demo app images)
- **OpenShift users**: May need to configure Security Context Constraints (SCC) for the operator

## 📁 Repository Structure

```
multitenant-opentelemetry-example/
├── deployment/              # OpenTelemetry Collector deployment mode config
│   └── deployment-collector.yaml  # OpenTelemetryCollector CRD
├── daemonset/               # OpenTelemetry Collector daemonset mode config
│   ├── daemonset-collector.yaml  # OpenTelemetryCollector CRD
│   ├── rbac.yaml            # RBAC resources
├── operator/                # OpenTelemetry Operator configuration
│   └── values.yaml          # Helm values for OpenTelemetry Operator
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
└── README.md                # This file
```

## 🚀 Quick Start

### 1. Install OpenTelemetry Operator

The OpenTelemetry Operator provides CRD-based management of OpenTelemetry Collectors and enables automatic instrumentation injection. You may already have the OpenTelemetry Operator running in your OpenShift cluster. If this is the case, you may need to adapt these instructions to your own environment.

**Install the operator:**

```bash
# Add the OpenTelemetry Helm repository (if not already added)
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Install the operator
helm install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace observability \
  --create-namespace \
  --values operator/values.yaml
```

**For OpenShift clusters**, you may need to configure Security Context Constraints (SCC) first:
```bash
oc adm policy add-scc-to-user hostmount-anyuid -z otel-collector -n observability
oc adm policy add-scc-to-user privileged -z otel-collector -n observability
```

**Verify installation:**
```bash
kubectl get pods -n observability
kubectl get crd | grep opentelemetry
```

### 2. Install OpenTelemetry Collector Custom Resources

Install the OpenTelemetry Collector in both deployment and daemonset modes.

**Create namespace and required secrets:**
```bash
kubectl create namespace observability
kubectl create secret generic newrelic-license-key \
  --from-literal=license-key='YOUR_NEW_RELIC_LICENSE_KEY' \
  -n observability
kubectl create secret generic newrelic-license-key-tenant1 \
  --from-literal=license-key='YOUR_TENANT1_LICENSE_KEY' \
  -n observability
kubectl create secret generic newrelic-license-key-tenant2 \
  --from-literal=license-key='YOUR_TENANT2_LICENSE_KEY' \
  -n observability
```

**Deployment Mode** (recommended for centralized collection and multi-tenant routing):
```bash
# Apply RBAC resources
kubectl apply -f daemonset/rbac.yaml

# Install the deployment collector using OpenTelemetryCollector custom resource
kubectl apply -f deployment/deployment-collector.yaml
```

**Daemonset Mode** (recommended for node, pod, container metrics and logs. forwards to deployment gateway):
```bash
# Install deployment gateway first (see above)
# Then install daemonset using OpenTelemetryCollector custom resource
kubectl apply -f daemonset/daemonset-collector.yaml
```

### 3. Build and Deploy Demo Application

```bash
cd demo-app

# Build Docker images (see demo-app/README.md for details)
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

📖 **Full demo app documentation**: See [demo-app/README.md](demo-app/README.md)

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

## 🔧 Configuration

### OpenTelemetry Collector

Configuration files are in `deployment/deployment-collector.yaml` and `daemonset/daemonset-collector.yaml`. These use the OpenTelemetry Operator's `OpenTelemetryCollector` CRD.

**Key components:**
- **OTLP Receivers**: Accept telemetry from applications
- **New Relic Exporters**: Multiple otlphttp exporters configured for per-tenant routing
- **Routing Connectors**: Routes telemetry by namespace to tenant-specific pipelines
- **Processors**: Resource detection, batch processing, cumulative-to-delta conversion, transforms
- **Pipelines**: Configured for traces, metrics, and logs with tenant-specific routing

📖 **Detailed configuration documentation**: See [CONFIGURATION.md](CONFIGURATION.md)

### Demo Application

Configuration is managed via Helm values. See `demo-app/helm/demo-app/values.yaml` for all available options.

📖 **Demo app configuration**: See [demo-app/README.md](demo-app/README.md)

### Automatic Instrumentation

The OpenTelemetry Operator can automatically inject OpenTelemetry instrumentation into your application pods using the `Instrumentation` CRD. The demo application uses manual instrumentation, but you can adapt it to use operator-based auto-instrumentation if desired.

📖 **More information**: See [OpenTelemetry Operator Documentation](https://github.com/open-telemetry/opentelemetry-operator)

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

The demo app includes a Locust-based load generator. See [demo-app/README.md](demo-app/README.md) for details on running load tests.

## 🔍 Troubleshooting

### Collector Not Receiving Telemetry

1. **Check collector pods are running:**
   ```bash
   kubectl get pods -n observability
   ```

2. **Check collector logs:**
   ```bash
   # Deployment mode
   kubectl logs -n observability -l app.kubernetes.io/name=opentelemetry-collector
   
   # Daemonset mode
   kubectl logs -n observability <daemonset-pod-name>
   ```

3. **Verify OTLP endpoint configuration:**
   - For deployment mode: Use service endpoint `opentelemetry-collector-deployment-collector.observability.svc.cluster.local:4317`
   - For daemonset mode: Use node IP (configured automatically via `status.hostIP`)

4. **Check routing configuration:**
   - Verify telemetry is being routed correctly by namespace
   - Check that tenant-specific exporters are receiving data
   - Review collector config in [CONFIGURATION.md](CONFIGURATION.md)

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

### Operator Issues

1. **Operator not working:**
   ```bash
   # Check operator pods are running
   kubectl get pods -n observability
   
   # Check operator logs
   kubectl logs -n observability -l app.kubernetes.io/name=opentelemetry-operator
   
   # Verify CRDs are installed
   kubectl get crd | grep opentelemetry
   ```

2. **Webhook admission errors:**
   ```bash
   # Check webhook configuration
   kubectl get mutatingwebhookconfigurations
   kubectl get validatingwebhookconfigurations
   ```

3. **OpenShift SCC issues:**
   ```bash
   # Apply SCC policies (see operator installation section)
   oc adm policy add-scc-to-user hostmount-anyuid -z otel-collector -n observability
   oc adm policy add-scc-to-user privileged -z otel-collector -n observability
   ```

## 📚 Documentation

- **[CONFIGURATION.md](CONFIGURATION.md)**: Detailed OpenTelemetry Collector configuration documentation
- **[demo-app/README.md](demo-app/README.md)**: Demo application documentation and usage guide
- **[demo-app/helm/demo-app/values.yaml](demo-app/helm/demo-app/values.yaml)**: Helm chart configuration reference

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
