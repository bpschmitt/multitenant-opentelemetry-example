# Multi-tenant OpenTelemetry Demo Application

This demo application consists of two Python services (sender and receiver) that communicate via HTTP and generate OpenTelemetry telemetry data (traces, metrics, and logs). The application is designed to be deployed in multiple Kubernetes namespaces to demonstrate multi-tenant OpenTelemetry collection.

## Architecture

The demo application consists of:

- **Sender Service**: Receives HTTP requests and forwards them to the receiver service
- **Receiver Service**: Processes requests and simulates database operations
- **Load Generator (Locust)**: Optional load generator for testing (can be deployed as deployment or job)

All services are instrumented with OpenTelemetry to generate:
- **Traces**: Distributed traces showing request flow from sender → receiver
- **Metrics**: Request counts, latency, error rates
- **Logs**: Structured application logs with trace correlation

The application will be deployed twice (once per tenant) in separate Kubernetes namespaces.

## Prerequisites

- Kubernetes cluster with kubectl configured
- Helm 3.x installed
- Docker (for building images)
- OpenTelemetry Collector deployed (see parent directory's INSTALL.md)

## Building the Docker Images

The Makefile supports building multi-platform Docker images (amd64 and arm64) using Docker buildx. This is useful for deploying to mixed-architecture Kubernetes clusters.

### Multi-Platform Builds (Recommended)

Build and push multi-platform images for both architectures:

```bash
# Build and push all services including loadgen (amd64 and arm64)
make build

# Or build without pushing (images in buildx cache only)
make build PUSH=false

# Or use the push target explicitly
make push
```

The Makefile will automatically:
- Set up Docker buildx if needed
- Build images for both `linux/amd64` and `linux/arm64` platforms
- Push to your registry (default: `demo-app/sender:latest` and `demo-app/receiver:latest`)

### Single-Platform Builds (Local Development)

For local development on a single architecture:

```bash
# Build for local use (single platform)
make build-local

# Or manually
cd sender
docker build -t demo-app/sender:latest .

cd ../receiver
docker build -t demo-app/receiver:latest .
```

### Customizing Build Settings

You can customize the build using Makefile variables:

```bash
# Use a different registry
make build REGISTRY=myregistry.io/demo-app

# Use a different tag
make build TAG=v1.0.0

# Build for specific platforms
make build PLATFORMS=linux/amd64,linux/arm64

# Build without pushing
make build PUSH=false
```

### Manual Build Commands

If you prefer to build manually:

```bash
# Set up buildx (one-time setup)
docker buildx create --name multiarch-builder --driver docker-container --use
docker buildx inspect --bootstrap

# Build and push multi-platform images
docker buildx build --platform linux/amd64,linux/arm64 \
  -t <registry>/demo-app/sender:latest --push ./sender

docker buildx build --platform linux/amd64,linux/arm64 \
  -t <registry>/demo-app/receiver:latest --push ./receiver
```

Update the `values.yaml` or tenant-specific values files with your image repository.

## Deployment

### Deploy Tenant 1

```bash
# Create namespace
kubectl create namespace tenant1-demo

# Install with Helm (using default images)
helm install demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --values ./helm/demo-app/values-tenant1.yaml \
  --set global.otlpEndpoint=http://opentelemetry-collector.otel-collector.svc.cluster.local:4317

# Or with custom images using global registry
helm install demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --values ./helm/demo-app/values-tenant1.yaml \
  --set global.otlpEndpoint=http://opentelemetry-collector.otel-collector.svc.cluster.local:4317 \
  --set global.imageRegistry=docker.io/myorg \
  --set sender.image.repository=sender \
  --set sender.image.tag=v1.0.0 \
  --set receiver.image.repository=receiver \
  --set receiver.image.tag=v1.0.0

# Or with full image paths
helm install demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --values ./helm/demo-app/values-tenant1.yaml \
  --set global.otlpEndpoint=http://opentelemetry-collector.otel-collector.svc.cluster.local:4317 \
  --set sender.image.repository=myregistry.io/myorg/sender \
  --set sender.image.tag=v1.0.0 \
  --set receiver.image.repository=myregistry.io/myorg/receiver \
  --set receiver.image.tag=v1.0.0
```

### Deploy Tenant 2

```bash
# Create namespace
kubectl create namespace tenant2-demo

# Install with Helm (using default images)
helm install demo-app-tenant2 ./helm/demo-app \
  --namespace tenant2-demo \
  --values ./helm/demo-app/values-tenant2.yaml \
  --set global.otlpEndpoint=http://opentelemetry-collector.otel-collector.svc.cluster.local:4317

# Or with custom images (same options as tenant 1)
helm install demo-app-tenant2 ./helm/demo-app \
  --namespace tenant2-demo \
  --values ./helm/demo-app/values-tenant2.yaml \
  --set global.otlpEndpoint=http://opentelemetry-collector.otel-collector.svc.cluster.local:4317 \
  --set global.imageRegistry=docker.io/myorg \
  --set sender.image.repository=sender \
  --set receiver.image.repository=receiver
```

### Using Makefile for Deployment

The Makefile supports image overrides:

```bash
# Deploy with custom registry
make deploy-tenant1 IMAGE_REGISTRY=docker.io/myorg TAG=v1.0.0

# Deploy with custom registry and tag
make deploy-tenant2 IMAGE_REGISTRY=ghcr.io/myorg TAG=latest
```

## Verify Deployment

Check that pods are running:

```bash
# Tenant 1
kubectl get pods -n tenant1-demo

# Tenant 2
kubectl get pods -n tenant2-demo
```

Check services:

```bash
# Tenant 1
kubectl get svc -n tenant1-demo

# Tenant 2
kubectl get svc -n tenant2-demo
```

## Generating Traffic

### Using curl

Port-forward to the sender service:

```bash
# Tenant 1
kubectl port-forward -n tenant1-demo svc/sender 8000:8000

# In another terminal
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"request_id": "test-123", "message": "Hello from tenant1"}'
```

### Using the Load Generator

The demo app includes a Locust-based load generator that can be deployed as a Kubernetes deployment or job.

**Deploy as a Deployment (with Web UI):**

```bash
# Enable loadgen in Helm values
helm upgrade demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --values ./helm/demo-app/values-tenant1.yaml \
  --set loadgen.enabled=true \
  --set loadgen.mode=deployment

# Port-forward to access Locust web UI
kubectl port-forward -n tenant1-demo svc/loadgen 8089:8089

# Open http://localhost:8089 in your browser to control the load test
```

**Deploy as a Job (Headless, One-time Run):**

```bash
# Run a one-time load test
helm upgrade demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --values ./helm/demo-app/values-tenant1.yaml \
  --set loadgen.enabled=true \
  --set loadgen.mode=job \
  --set loadgen.job.users=20 \
  --set loadgen.job.spawnRate=5 \
  --set loadgen.job.runTime=10m
```

**Configure Load Test Parameters:**

```bash
helm upgrade demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --set loadgen.enabled=true \
  --set loadgen.mode=deployment \
  --set loadgen.env.TARGET_HOST=http://sender-service:8000
```

## Configuration

### Image Configuration

The Helm chart supports flexible image configuration:

#### Option 1: Global Image Registry

Set a global registry that applies to all services:

```yaml
# values-tenant1.yaml
global:
  imageRegistry: "docker.io/myorg"
  # or "ghcr.io/myorg"
  # or "myregistry.io"

sender:
  image:
    repository: "sender"  # Results in: docker.io/myorg/sender
    tag: "v1.0.0"

receiver:
  image:
    repository: "receiver"  # Results in: docker.io/myorg/receiver
    tag: "v1.0.0"
```

#### Option 2: Full Image Paths

Specify complete image paths without a global registry:

```yaml
sender:
  image:
    repository: "docker.io/myorg/sender"
    tag: "v1.0.0"
```

#### Option 3: Command Line Overrides

Override images during deployment:

```bash
helm install demo-app-tenant1 ./helm/demo-app \
  --set global.imageRegistry=docker.io/myorg \
  --set sender.image.repository=sender \
  --set sender.image.tag=v1.0.0 \
  --set receiver.image.repository=receiver \
  --set receiver.image.tag=v1.0.0
```

#### Image Pull Secrets

Configure image pull secrets for private registries:

```yaml
global:
  imagePullSecrets:
    - my-registry-secret

# Or per-service
sender:
  image:
    pullSecrets:
      - sender-registry-secret
```

### OTLP Endpoint Configuration

The Helm chart supports two modes for configuring the OTLP endpoint:

#### Option 1: Node-Local Endpoint (Default - for Daemonset Collectors)

When using OpenTelemetry Collector in daemonset mode, each node has a collector running. The application will automatically use the node's IP address:

```yaml
global:
  useNodeLocalEndpoint: true  # Default
  otlpPort: "4317"  # Port for node-local endpoint
```

The application will:
1. Read `NODE_IP` from Kubernetes downward API (`status.hostIP`)
2. Construct the endpoint as `http://<NODE_IP>:4317`
3. Fall back to a default if `NODE_IP` is not available

#### Option 2: Specific Endpoint (for Deployment Collectors)

When using OpenTelemetry Collector in deployment mode, use a specific endpoint:

```yaml
global:
  useNodeLocalEndpoint: false
  otlpEndpoint: "http://opentelemetry-collector.otel-collector.svc.cluster.local:4317"
```

#### Override via Command Line

```bash
# Use node-local endpoint (default)
helm install demo-app-tenant1 ./helm/demo-app \
  --set global.useNodeLocalEndpoint=true

# Use specific endpoint
helm install demo-app-tenant1 ./helm/demo-app \
  --set global.useNodeLocalEndpoint=false \
  --set global.otlpEndpoint=http://custom-collector:4317
```

### Environment Variables

Both services support the following environment variables:

- `OTEL_SERVICE_NAME`: Service name for OpenTelemetry (default: "sender-service" or "receiver-service")
- `TENANT_ID`: Tenant identifier (set via Helm values)
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP collector endpoint (constructed from NODE_IP if not set)
- `NODE_IP`: Node IP address (set automatically when useNodeLocalEndpoint=true)
- `OTLP_PORT`: Port for OTLP endpoint (default: "4317")
- `RECEIVER_SERVICE_URL`: URL of receiver service (sender only)
- `ERROR_RATE`: Error simulation rate (0.0 to 1.0)
- `LATENCY_MS`: Artificial latency in milliseconds
- `PROCESSING_TIME_MS`: Processing time simulation (receiver only)

### Customizing Tenant Behavior

Edit the tenant-specific values files to customize behavior:

- `helm/demo-app/values-tenant1.yaml`
- `helm/demo-app/values-tenant2.yaml`

Example: Enable error simulation and custom images for tenant 2:

```yaml
# values-tenant2.yaml
global:
  imageRegistry: "docker.io/myorg"

sender:
  image:
    repository: "sender"
    tag: "v1.0.0"
  env:
    ERROR_RATE: "0.1"  # 10% error rate
```

## Viewing Telemetry

Telemetry data is sent to the OpenTelemetry Collector, which should forward it to your observability backend (e.g., New Relic).

### Check Collector Logs

```bash
kubectl logs -n otel-collector -l app.kubernetes.io/name=opentelemetry-collector --tail=50
```

### Verify Traces

Check your observability platform (New Relic, Jaeger, etc.) for traces. You should see:
- Traces with spans from both sender and receiver services
- Tenant-specific attributes (`tenant.id`, `k8s.namespace`)
- Service names like `sender-service-tenant1` and `receiver-service-tenant1`

## Service Endpoints

### Sender Service

- `GET /health` - Health check
- `POST /send` - Send a request to receiver
- `GET /metrics` - Metrics info (OTLP metrics exported separately)

### Receiver Service

- `GET /health` - Health check
- `POST /process` - Process a request (called by sender)
- `GET /metrics` - Metrics info (OTLP metrics exported separately)

### Load Generator (Locust)

When deployed as a deployment:
- `http://loadgen-service:8089` - Locust web UI (port-forward to access)

The load generator sends requests to the sender service's `/send` and `/health` endpoints.

## Example Request

```bash
curl -X POST http://sender-service.tenant1-demo.svc.cluster.local:8000/send \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-001",
    "message": "Test message",
    "data": {
      "key": "value"
    }
  }'
```

## Troubleshooting

### Pods not starting

Check pod logs:

```bash
kubectl logs -n tenant1-demo -l app=sender
kubectl logs -n tenant1-demo -l app=receiver
```

### Services can't communicate

Verify service DNS:

```bash
kubectl exec -n tenant1-demo -it <sender-pod> -- nslookup receiver-service
```

### No telemetry data

1. Verify OTLP endpoint is correct in Helm values
2. Check OpenTelemetry Collector is running and accessible
3. Check collector logs for errors
4. Verify network policies allow traffic to collector

### Build errors

Ensure Docker images are built and available:

```bash
docker images | grep demo-app
```

## Upgrading

To upgrade a deployment:

```bash
helm upgrade demo-app-tenant1 ./helm/demo-app \
  --namespace tenant1-demo \
  --values ./helm/demo-app/values-tenant1.yaml
```

## Uninstalling

```bash
# Tenant 1
helm uninstall demo-app-tenant1 -n tenant1-demo
kubectl delete namespace tenant1-demo

# Tenant 2
helm uninstall demo-app-tenant2 -n tenant2-demo
kubectl delete namespace tenant2-demo
```

## Development

### Local Development

Run services locally (requires OpenTelemetry Collector running):

```bash
# Terminal 1 - Receiver
cd receiver
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=receiver-service
export TENANT_ID=local
python app.py

# Terminal 2 - Sender
cd sender
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=sender-service
export RECEIVER_SERVICE_URL=http://localhost:8001
export TENANT_ID=local
python app.py
```

### Testing

Test the sender endpoint:

```bash
curl -X POST http://localhost:8000/send \
  -H "Content-Type: application/json" \
  -d '{"request_id": "test", "message": "hello"}'
```

## License

This is a demo application for educational purposes.

