# OpenTelemetry Collector Helm Deployment

This directory contains Helm-based configurations for deploying OpenTelemetry Collectors directly using Helm charts.

## Overview

This deployment method uses Helm charts to install OpenTelemetry Collectors directly, without requiring the OpenTelemetry Operator. This provides more direct control over the deployment.

## Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x
- kubectl configured
- New Relic account with license keys:
  - Default license key (for non-tenant namespaces)
  - Tenant 1 license key (optional, for tenant1-demo namespace)
  - Tenant 2 license key (optional, for tenant2-demo namespace)

## Installation

### 1. Add Helm Repository

```bash
# Add the OpenTelemetry Helm repository
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
```

### 2. Create Namespace and Secrets

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

### 3. Deploy Collectors

#### Deployment Mode (Recommended for centralized collection)

```bash
helm install opentelemetry-collector-deployment open-telemetry/opentelemetry-collector \
  --namespace observability \
  --create-namespace \
  --values deployment/values.yaml
```

#### Daemonset Mode (Recommended for node-level metrics and logs)

```bash
helm install opentelemetry-collector-daemonset open-telemetry/opentelemetry-collector \
  --namespace observability \
  --create-namespace \
  --values daemonset/values.yaml
```

**Note**: If you install both deployment and daemonset, use different Helm release names to avoid conflicts.

## Configuration Files

- **`deployment/values.yaml`**: Helm values for deployment mode collector
- **`deployment/manifest.yaml`**: Generated manifest (for reference)
- **`daemonset/values.yaml`**: Helm values for daemonset mode collector
- **`daemonset/manifest.yaml`**: Generated manifest (for reference)

## Features

- **Direct Control**: Full control over Helm release configuration
- **No Operator Required**: Deploy collectors without installing the operator
- **Helm-native**: Uses standard Helm workflows and tooling
- **Multi-tenant Support**: Routes telemetry by namespace using routing connectors

## Upgrading

```bash
# Upgrade deployment mode
helm upgrade opentelemetry-collector-deployment open-telemetry/opentelemetry-collector \
  --namespace observability \
  --values deployment/values.yaml

# Upgrade daemonset mode
helm upgrade opentelemetry-collector-daemonset open-telemetry/opentelemetry-collector \
  --namespace observability \
  --values daemonset/values.yaml
```

## Uninstalling

```bash
# Uninstall deployment mode
helm uninstall opentelemetry-collector-deployment --namespace observability

# Uninstall daemonset mode
helm uninstall opentelemetry-collector-daemonset --namespace observability
```

## Troubleshooting

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

3. **Verify Helm release status:**
   ```bash
   helm list -n observability
   helm status opentelemetry-collector-deployment -n observability
   ```

4. **Verify OTLP endpoint configuration:**
   - For deployment mode: Use service endpoint `opentelemetry-collector-deployment-collector.observability.svc.cluster.local:4317`
   - For daemonset mode: Use node IP (configured via environment variables)


## Related Documentation

- **[../../CONFIGURATION.md](../../CONFIGURATION.md)**: Detailed collector configuration documentation
- **[../../README.md](../../README.md)**: Main repository README
- [OpenTelemetry Collector Helm Chart](https://github.com/open-telemetry/opentelemetry-helm-charts)
