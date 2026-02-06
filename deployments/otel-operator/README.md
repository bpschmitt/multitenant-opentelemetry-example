# OpenTelemetry Operator Deployment

This directory contains configurations for deploying OpenTelemetry Collectors using the OpenTelemetry Operator with Custom Resource Definitions (CRDs).

## Overview

The OpenTelemetry Operator provides CRD-based management of OpenTelemetry Collectors and enables automatic instrumentation injection. This is the recommended approach for production deployments.

## Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x
- kubectl configured
- cert-manager installed
- New Relic account with license keys:
  - Default license key (for non-tenant namespaces)
  - Tenant 1 license key (optional, for tenant1-demo namespace)
  - Tenant 2 license key (optional, for tenant2-demo namespace)
- **OpenShift users**: May need to configure Security Context Constraints (SCC)

## Installation

### 1. Install cert-manager

The OpenTelemetry Operator requires cert-manager for webhook certificate management.

```bash
# Install cert-manager using Helm
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install cert-manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true

# Verify installation
kubectl get pods -n cert-manager
```

**Alternative installation method (kubectl):**
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

**Verify cert-manager is ready:**
```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s
```

### 2. Install OpenTelemetry Operator

```bash
# Add the OpenTelemetry Helm repository (if not already added)
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

# Install the operator
helm upgrade --install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace observability \
  --create-namespace \
  --values operator/values.yaml
```

**Apply RBAC resources** (required before deploying any collectors):
```bash
# RBAC must be applied before deploying gateway, deployment, or daemonset collectors
# All collectors use the same otel-collector service account
kubectl apply -f rbac/rbac.yaml
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

### 3. Create Secrets

```bash
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

### 4. Deploy Collectors

The gateway collector must be deployed first, as both the deployment and daemonset collectors send telemetry to it. The gateway then forwards all telemetry to New Relic.

#### Gateway Collector (Required)

The gateway collector acts as the central hub that receives telemetry from other collectors and forwards it to New Relic.

```bash
# Install the gateway collector using OpenTelemetryCollector custom resource
# This must be deployed before deployment or daemonset collectors
kubectl apply -f gateway/gateway-collector.yaml
```

#### Deployment Mode (Recommended for centralized collection and multi-tenant routing)

The deployment collector sends telemetry to the gateway collector.

```bash
# Install the deployment collector using OpenTelemetryCollector custom resource
kubectl apply -f deployment/deployment-collector.yaml
```

#### Daemonset Mode (Recommended for node, pod, container metrics and logs)

The daemonset collector sends telemetry to the gateway collector.

```bash
# Install daemonset using OpenTelemetryCollector custom resource
# Ensure the gateway collector is deployed first (see Gateway Collector above)
kubectl apply -f daemonset/daemonset-collector.yaml
```

## Configuration Files

- **`operator/values.yaml`**: Helm values for OpenTelemetry Operator installation
- **`gateway/gateway-collector.yaml`**: OpenTelemetryCollector CRD for gateway mode (central hub that receives telemetry from other collectors)
- **`deployment/deployment-collector.yaml`**: OpenTelemetryCollector CRD for deployment mode
- **`daemonset/daemonset-collector.yaml`**: OpenTelemetryCollector CRD for daemonset mode
- **`rbac/rbac.yaml`**: RBAC resources (ServiceAccount, ClusterRole, ClusterRoleBinding)

## Features

- **CRD-based Management**: Declarative collector configuration using `OpenTelemetryCollector` CRDs
- **Automatic Instrumentation**: Inject OpenTelemetry instrumentation into pods automatically
- **Simplified Deployment**: No need to manage Helm releases for collectors
- **Better Integration**: Works seamlessly with Kubernetes-native tooling
- **Multi-tenant Support**: Routes telemetry by namespace using routing connectors

## Automatic Instrumentation

The operator can automatically inject OpenTelemetry instrumentation into your application pods using the `Instrumentation` CRD:

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: my-instrumentation
  namespace: tenant1-demo
spec:
  exporter:
    endpoint: http://opentelemetry-collector-deployment-collector.observability.svc.cluster.local:4317
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

📖 **More information**: See [OpenTelemetry Operator Documentation](https://github.com/open-telemetry/opentelemetry-operator)

## Troubleshooting

### Operator Not Working

1. **Check operator pods are running:**
   ```bash
   kubectl get pods -n observability
   ```

2. **Check operator logs:**
   ```bash
   kubectl logs -n observability -l app.kubernetes.io/name=opentelemetry-operator
   ```

3. **Verify CRDs are installed:**
   ```bash
   kubectl get crd | grep opentelemetry
   ```

### Webhook Admission Errors

```bash
# Check webhook configuration
kubectl get mutatingwebhookconfigurations
kubectl get validatingwebhookconfigurations

# Check webhook service
kubectl get svc -n observability
```

### OpenShift SCC Issues

```bash
# Apply SCC policies
oc adm policy add-scc-to-user hostmount-anyuid -z otel-collector -n observability
oc adm policy add-scc-to-user privileged -z otel-collector -n observability
```

### Collector Not Receiving Telemetry

1. **Check collector pods:**
   ```bash
   kubectl get pods -n observability
   kubectl get opentelemetrycollector -n observability
   ```

2. **Check collector logs:**
   ```bash
   kubectl logs -n observability -l app.kubernetes.io/name=opentelemetry-collector
   ```

3. **Verify OTLP endpoint configuration:**
   - For deployment mode: Use service endpoint `opentelemetry-collector-deployment-collector.observability.svc.cluster.local:4317`
   - For daemonset mode: Use node IP (configured automatically via `status.hostIP`)

## Related Documentation

- **[../../CONFIGURATION.md](../../CONFIGURATION.md)**: Detailed collector configuration documentation
- **[../../README.md](../../README.md)**: Main repository README
- [OpenTelemetry Operator](https://github.com/open-telemetry/opentelemetry-operator)
