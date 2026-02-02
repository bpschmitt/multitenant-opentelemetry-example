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
├── deployment/              # OpenTelemetry Collector deployment mode config
│   └── deployment-values.yaml  # Helm values for deployment mode
├── daemonset/               # OpenTelemetry Collector daemonset mode config
│   └── daemonset-values.yaml  # Helm values for daemonset mode
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
├── INSTALL.md              # OpenTelemetry Collector installation guide
└── README.md              # This file
```

## 🚀 Quick Start

### 1. Install OpenTelemetry Operator (Optional but Recommended)

The OpenTelemetry Operator provides CRD-based management of OpenTelemetry Collectors and enables automatic instrumentation injection. This is the recommended approach for production deployments.

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

Once the operator is installed, you can use `OpenTelemetryCollector` CRDs instead of Helm charts (see "Using the Operator" section below).

**Note**: You can use either the operator (CRD-based) or Helm charts directly. The operator provides additional features like automatic instrumentation injection.

### 2. Install OpenTelemetry Collector

Choose either deployment or daemonset mode based on your needs:

**Deployment Mode** (recommended for centralized collection and multi-tenant routing):
```bash
# Create required secrets first (see INSTALL.md)
kubectl create namespace otel-collector
kubectl create secret generic newrelic-license-key \
  --from-literal=license-key='YOUR_NEW_RELIC_LICENSE_KEY' \
  -n otel-collector
kubectl create secret generic newrelic-license-key-tenant1 \
  --from-literal=license-key='YOUR_TENANT1_LICENSE_KEY' \
  -n otel-collector
kubectl create secret generic newrelic-license-key-tenant2 \
  --from-literal=license-key='YOUR_TENANT2_LICENSE_KEY' \
  -n otel-collector

# Install the collector
helm install opentelemetry-collector open-telemetry/opentelemetry-collector \
  --namespace otel-collector \
  --create-namespace \
  --values deployment/deployment-values.yaml
```

**Daemonset Mode** (recommended for node-level metrics and logs, forwards to deployment gateway):
```bash
# Install deployment gateway first (see above)
# Then install daemonset (use a different release name to avoid conflicts)
helm install opentelemetry-collector-daemonset open-telemetry/opentelemetry-collector \
  --namespace otel-collector \
  --create-namespace \
  --values daemonset/daemonset-values.yaml
```

**Note**: If you install both deployment and daemonset, use different Helm release names (e.g., `opentelemetry-collector` for deployment and `opentelemetry-collector-daemonset` for daemonset).

**Hybrid Mode** (recommended): Deploy both - daemonset for node-level collection, deployment for centralized routing.

📖 **Full installation instructions**: See [INSTALL.md](INSTALL.md)

### 3. Build and Deploy Demo Application

```bash
cd demo-app

# Build Docker images (see demo-app/README.md for details)
# Update imageRegistry in values-tenant1.yaml and values-tenant2.yaml first
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

**Note**: The demo app is configured to use node-local endpoints by default (for daemonset mode). If using deployment mode only, update the values files to set `useNodeLocalEndpoint: false` and configure `otlpEndpoint`.

📖 **Full demo app documentation**: See [demo-app/README.md](demo-app/README.md)

## 🔧 Using the OpenTelemetry Operator

If you've installed the OpenTelemetry Operator, you can manage collectors using Custom Resource Definitions (CRDs) instead of Helm charts. This provides several benefits:

- **CRD-based management**: Declarative collector configuration
- **Automatic instrumentation**: Inject OpenTelemetry instrumentation into pods automatically
- **Simplified deployment**: No need to manage Helm releases for collectors
- **Better integration**: Works seamlessly with Kubernetes-native tooling

### Deploying Collectors with the Operator

Instead of using Helm charts, you can create `OpenTelemetryCollector` custom resources. The operator will automatically create and manage the collector deployments.

**Example: Deployment Mode Collector**

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel-collector
  namespace: otel-collector
spec:
  mode: deployment
  config: |
    # Your collector configuration here
    # (same as in deployment/deployment-values.yaml config section)
```

**Example: Daemonset Mode Collector**

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel-collector-daemonset
  namespace: otel-collector
spec:
  mode: daemonset
  config: |
    # Your collector configuration here
    # (same as in daemonset/daemonset-values.yaml config section)
```

### Automatic Instrumentation

The operator can automatically inject OpenTelemetry instrumentation into your application pods using the `Instrumentation` CRD:

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: my-instrumentation
  namespace: tenant1
spec:
  exporter:
    endpoint: http://otel-collector.otel-collector.svc.cluster.local:4317
  propagators:
    - tracecontext
    - baggage
  sampler:
    type: parentbased_traceidratio
    argument: "1"
```

Then annotate your pods/deployments to enable instrumentation:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    metadata:
      annotations:
        instrumentation.opentelemetry.io/inject-python: "true"
        instrumentation.opentelemetry.io/inject-java: "true"
        # etc.
```

**Note**: The demo application in this repository uses manual instrumentation, but you can adapt it to use operator-based auto-instrumentation if desired.

📖 **More information**: See [OpenTelemetry Operator Documentation](https://github.com/open-telemetry/opentelemetry-operator)

## 🏗️ Architecture

### Multi-Tenant Routing

This example demonstrates a multi-tenant OpenTelemetry collection architecture:

1. **Application Layer**: Demo applications deployed in separate Kubernetes namespaces (`tenant1`, `tenant2`)
2. **Collection Layer**: 
   - **Daemonset Collectors**: Collect node-level metrics, logs, and kubelet metrics from each node
   - **Deployment Gateway**: Centralized collector that receives telemetry from daemonset collectors and applications
3. **Routing Layer**: OpenTelemetry routing connectors route telemetry based on `k8s.namespace.name` attribute:
   - `tenant1` namespace → `otlphttp/tenant1` exporter (uses `NEW_RELIC_LICENSE_KEY_TENANT1`)
   - `tenant2` namespace → `otlphttp/tenant2` exporter (uses `NEW_RELIC_LICENSE_KEY_TENANT2`)
   - Other namespaces → `otlphttp/newrelic` exporter (uses `NEW_RELIC_LICENSE_KEY`)
4. **Export Layer**: Each tenant's telemetry is exported to New Relic using tenant-specific license keys

### Data Flow

```
Application Pods (tenant1/tenant2)
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

## 🎯 Features

### OpenTelemetry Collector

- **Deployment Mode**: Centralized collection, Kubernetes events, cluster metrics, multi-tenant routing
- **Daemonset Mode**: Node-level metrics, host logs, kubelet metrics (can forward to deployment gateway)
- **Multi-tenant Support**: Routes telemetry by namespace/tenant ID using routing connectors
- **New Relic Integration**: Configured to export to New Relic OTLP endpoint with per-tenant license keys
- **Resource Attributes**: Automatically enriches telemetry with Kubernetes metadata
- **Hybrid Architecture**: Daemonset collectors can forward to deployment gateway for centralized routing
- **Operator Support**: CRD-based management via OpenTelemetry Operator (optional)

### OpenTelemetry Operator (Optional)

- **CRD-based Management**: Declarative collector configuration using `OpenTelemetryCollector` CRDs
- **Automatic Instrumentation**: Inject OpenTelemetry SDKs into pods using `Instrumentation` CRDs
- **Webhook-based Injection**: Automatic sidecar and instrumentation injection via admission webhooks
- **Multi-language Support**: Auto-instrumentation for Java, Python, Node.js, .NET, Go, and Apache HTTPd

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
- `k8s.namespace.name` - Kubernetes namespace (used for routing)
- `k8s.pod.name` - Kubernetes pod name
- `k8s.pod.ip` - Kubernetes pod IP address

## 🔧 Configuration

### Installation Options

You can install the OpenTelemetry Collector using either:

1. **Helm Charts** (direct installation) - See sections below
2. **OpenTelemetry Operator** (CRD-based) - See "Using the OpenTelemetry Operator" section above

Both methods are supported. The operator provides additional features like automatic instrumentation injection, while Helm charts offer more direct control over the deployment.

### OpenTelemetry Collector

Configuration files are in `deployment/deployment-values.yaml` and `daemonset/daemonset-values.yaml`. Key settings:

- **OTLP Receivers**: Accept telemetry from applications
- **New Relic Exporters**: Multiple exporters configured for per-tenant routing
- **Routing Connectors**: Routes telemetry by namespace to tenant-specific pipelines
- **Processors**: Resource detection, batch processing, cumulative-to-delta conversion, transforms
- **Pipelines**: Configured for traces, metrics, and logs with tenant-specific routing

#### Deployment Mode Multi-Tenant Routing

The deployment mode uses routing connectors to route telemetry based on Kubernetes namespace:
- Telemetry from `tenant1` namespace → `otlphttp/tenant1` exporter
- Telemetry from `tenant2` namespace → `otlphttp/tenant2` exporter
- Other namespaces → default `otlphttp/newrelic` exporter

This requires separate New Relic license keys for each tenant:
- `newrelic-license-key` (default)
- `newrelic-license-key-tenant1`
- `newrelic-license-key-tenant2`

#### Daemonset Mode Gateway Pattern

The daemonset mode is configured to forward telemetry to a deployment gateway:
- Collects node-level metrics, logs, and kubelet metrics
- Forwards to `opentelemetry-collector-deployment.otel-collector.svc.cluster.local:4318`
- The deployment gateway then handles multi-tenant routing

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
   # Deployment mode (adjust release name if different)
   kubectl logs -n otel-collector -l app.kubernetes.io/name=opentelemetry-collector
   
   # Daemonset mode (adjust release name if different)
   kubectl logs -n otel-collector -l app.kubernetes.io/name=opentelemetry-collector
   # Or by pod name
   kubectl logs -n otel-collector <daemonset-pod-name>
   ```

3. **Verify OTLP endpoint configuration:**
   - For deployment mode: Use service endpoint `opentelemetry-collector.otel-collector.svc.cluster.local:4317`
   - For daemonset mode: Use node IP (configured automatically via `status.hostIP`)

4. **Check routing configuration:**
   - Verify telemetry is being routed correctly by namespace
   - Check that tenant-specific exporters are receiving data
   - Review collector config for routing connector setup

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

### Operator Issues

1. **Operator not injecting instrumentation:**
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
   
   # Check webhook service
   kubectl get svc -n observability
   ```

3. **OpenShift SCC issues:**
   ```bash
   # Apply SCC policies (see operator installation section)
   oc adm policy add-scc-to-user hostmount-anyuid -z otel-collector -n observability
   oc adm policy add-scc-to-user privileged -z otel-collector -n observability
   ```

## 🛠️ Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x (for Helm-based installation)
- kubectl configured
- Docker (for building images)
- New Relic account with license keys:
  - Default license key (for non-tenant namespaces)
  - Tenant 1 license key (optional, for tenant1 namespace)
  - Tenant 2 license key (optional, for tenant2 namespace)
- Docker registry access (for pushing demo app images)
- **OpenShift users**: May need to configure Security Context Constraints (SCC) for the operator

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
