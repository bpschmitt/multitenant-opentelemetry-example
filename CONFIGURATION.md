# OpenTelemetry Collector Configuration

This document describes the OpenTelemetry components configured in the deployment and daemonset collectors.

## Overview

This deployment uses two OpenTelemetry Collector configurations:

- **Deployment Collector** (`deployments/otel-operator/deployment/deployment-collector.yaml`): Centralized gateway for multi-tenant routing and cluster-level metrics
- **Daemonset Collector** (`deployments/otel-operator/daemonset/daemonset-collector.yaml`): Node-level agent for collecting host metrics, logs, and kubelet stats

## Deployment Collector

The deployment collector acts as a centralized gateway that:
- Receives telemetry from applications and the daemonset collectors
- Routes telemetry to tenant-specific exporters based on Kubernetes namespace
- Collects cluster-level Kubernetes metrics and events
- Exports to New Relic with per-tenant license keys

### Receivers

#### `otlp`
- **Purpose**: Receives OpenTelemetry Protocol (OTLP) telemetry from applications and daemonset collectors
- **Protocols**:
  - gRPC: `0.0.0.0:4317` (using `${env:MY_POD_IP}`)
  - HTTP: `0.0.0.0:4318` (using `${env:MY_POD_IP}`)
- **Used in pipelines**: `logs/in`, `metrics/in`, `traces/in`

#### `k8s_cluster`
- **Purpose**: Collects Kubernetes cluster-level metrics (nodes, pods, deployments, etc.)
- **Configuration**:
  - `collection_interval: 30s`
- **Used in pipeline**: `metrics/in`

#### `k8s_events`
- **Purpose**: Collects Kubernetes events from the cluster
- **Used in pipeline**: `logs`

### Processors

#### `memory_limiter`
- **Purpose**: Prevents the collector from using excessive memory
- **Configuration**:
  - `check_interval: 5s`
  - `limit_percentage: 80` - Triggers when memory usage exceeds 80%
  - `spike_limit_percentage: 25` - Allows spikes up to 25% above limit
- **Used in**: All pipelines

#### `batch`
- **Purpose**: Batches telemetry data to reduce the number of outgoing requests
- **Configuration**: Default settings
- **Used in**: All pipelines

#### `cumulativetodelta`
- **Purpose**: Converts cumulative metrics to delta metrics (required for some backends)
- **Configuration**: Default settings
- **Used in**: Metrics pipelines only

#### `transform/nr`
- **Purpose**: Transforms metrics to add New Relic-specific attributes
- **Configuration**:
  - Sets `newrelic.entity.type` to `"k8s"` for metrics from kubeletstats, k8scluster, and k8sevents receivers
- **Used in**: Metrics pipelines

### Connectors (Routing)

The deployment collector uses routing connectors to implement multi-tenant routing based on Kubernetes namespace.

#### `routing/logs`
- **Purpose**: Routes logs to tenant-specific pipelines based on `k8s.namespace.name`
- **Configuration**:
  - Default pipeline: `logs` (for non-tenant namespaces)
  - `tenant1-demo` namespace → `logs/tenant1` pipeline
  - `tenant2-demo` namespace → `logs/tenant2` pipeline
- **Used in pipelines**: `logs/in` (as exporter), `logs/tenant1`, `logs/tenant2` (as receiver)

#### `routing/metrics`
- **Purpose**: Routes metrics to tenant-specific pipelines based on `k8s.namespace.name`
- **Configuration**:
  - Default pipeline: `metrics` (for non-tenant namespaces)
  - `tenant1-demo` namespace → `metrics/tenant1` pipeline
  - `tenant2-demo` namespace → `metrics/tenant2` pipeline
- **Used in pipelines**: `metrics/in` (as exporter), `metrics/tenant1`, `metrics/tenant2` (as receiver)

#### `routing/traces`
- **Purpose**: Routes traces to tenant-specific pipelines based on `k8s.namespace.name`
- **Configuration**:
  - `tenant1-demo` namespace → `traces/tenant1` pipeline
  - `tenant2-demo` namespace → `traces/tenant2` pipeline
- **Used in pipelines**: `traces/in` (as exporter), `traces/tenant1`, `traces/tenant2` (as receiver)

### Exporters

#### `otlphttp/newrelic`
- **Purpose**: Exports telemetry to New Relic using the default license key
- **Configuration**:
  - `endpoint: https://otlp.nr-data.net`
  - `api-key: ${NEW_RELIC_LICENSE_KEY}`
- **Used in pipelines**: `logs`, `metrics`, `traces`

#### `otlphttp/tenant1`
- **Purpose**: Exports tenant1 telemetry to New Relic using tenant1 license key
- **Configuration**:
  - `endpoint: https://otlp.nr-data.net`
  - `api-key: ${NEW_RELIC_LICENSE_KEY_TENANT1}`
- **Used in pipelines**: `logs/tenant1`, `metrics/tenant1`, `traces/tenant1`

#### `otlphttp/tenant2`
- **Purpose**: Exports tenant2 telemetry to New Relic using tenant2 license key
- **Configuration**:
  - `endpoint: https://otlp.nr-data.net`
  - `api-key: ${NEW_RELIC_LICENSE_KEY_TENANT2}`
- **Used in pipelines**: `logs/tenant2`, `metrics/tenant2`, `traces/tenant2`

#### `debug`
- **Purpose**: Logs telemetry data to collector logs (useful for debugging)
- **Configuration**: Default settings
- **Used in pipelines**: `logs`, `logs/tenant1`, `logs/tenant2`, `metrics`, `traces/tenant1`

### Extensions

#### `health_check`
- **Purpose**: Provides health check endpoint for Kubernetes liveness/readiness probes
- **Configuration**:
  - `endpoint: ${env:MY_POD_IP}:13133`
- **Used in**: Service extensions

### Pipelines

#### Logs Pipelines

**`logs`**: Default logs pipeline for non-tenant namespaces
- Receivers: `routing/logs`, `k8s_events`
- Processors: `memory_limiter`, `batch`
- Exporters: `debug`, `otlphttp/newrelic`

**`logs/in`**: Ingress pipeline for all incoming logs
- Receivers: `otlp`
- Exporters: `routing/logs` (routes to tenant-specific or default pipeline)

**`logs/tenant1`**: Tenant1-specific logs pipeline
- Receivers: `routing/logs`
- Processors: `memory_limiter`, `batch`
- Exporters: `debug`, `otlphttp/tenant1`

**`logs/tenant2`**: Tenant2-specific logs pipeline
- Receivers: `routing/logs`
- Processors: `memory_limiter`, `batch`
- Exporters: `debug`, `otlphttp/tenant2`

#### Metrics Pipelines

**`metrics`**: Default metrics pipeline for non-tenant namespaces
- Receivers: `routing/metrics`
- Processors: `memory_limiter`, `cumulativetodelta`, `transform/nr`, `batch`
- Exporters: `debug`, `otlphttp/newrelic`

**`metrics/in`**: Ingress pipeline for all incoming metrics
- Receivers: `otlp`, `k8s_cluster`
- Exporters: `routing/metrics` (routes to tenant-specific or default pipeline)

**`metrics/tenant1`**: Tenant1-specific metrics pipeline
- Receivers: `routing/metrics`
- Processors: `memory_limiter`, `cumulativetodelta`, `transform/nr`, `batch`
- Exporters: `otlphttp/tenant1`

**`metrics/tenant2`**: Tenant2-specific metrics pipeline
- Receivers: `routing/metrics`
- Processors: `memory_limiter`, `cumulativetodelta`, `transform/nr`, `batch`
- Exporters: `otlphttp/tenant2`

#### Traces Pipelines

**`traces`**: Default traces pipeline for non-tenant namespaces
- Receivers: `routing/traces`
- Processors: `memory_limiter`, `batch`
- Exporters: `otlphttp/newrelic`

**`traces/in`**: Ingress pipeline for all incoming traces
- Receivers: `otlp`
- Exporters: `routing/traces` (routes to tenant-specific pipeline)

**`traces/tenant1`**: Tenant1-specific traces pipeline
- Receivers: `routing/traces`
- Processors: `memory_limiter`, `batch`
- Exporters: `otlphttp/tenant1`, `debug`

**`traces/tenant2`**: Tenant2-specific traces pipeline
- Receivers: `routing/traces`
- Processors: `memory_limiter`, `batch`
- Exporters: `otlphttp/tenant2`

### Environment Variables

- `MY_POD_IP`: Pod IP address (from `status.podIP`)
- `K8S_NODE_NAME`: Kubernetes node name (from `spec.nodeName`)
- `K8S_NODE_IP`: Kubernetes node IP (from `status.hostIP`)
- `NEW_RELIC_LICENSE_KEY`: Default New Relic license key (from secret)
- `NEW_RELIC_LICENSE_KEY_TENANT1`: Tenant1 New Relic license key (from secret)
- `NEW_RELIC_LICENSE_KEY_TENANT2`: Tenant2 New Relic license key (from secret)
- `K8S_CLUSTER_NAME`: Cluster name (set to `"openshift"`)

## Daemonset Collector

The daemonset collector runs on each node and:
- Collects host-level metrics (CPU, memory, disk, network)
- Collects Kubernetes pod/container metrics from kubelet
- Collects container logs from the node filesystem
- Forwards all telemetry to the deployment collector gateway

### Receivers

#### `otlp`
- **Purpose**: Receives OTLP telemetry from applications running on the node
- **Protocols**:
  - gRPC: `0.0.0.0:4317` (listens on all interfaces)
  - HTTP: `0.0.0.0:4318` (listens on all interfaces)
- **Note**: Uses `0.0.0.0` instead of pod IP because `hostNetwork: true` is enabled
- **Used in pipelines**: `logs`, `metrics`, `traces`

#### `filelog`
- **Purpose**: Collects container logs from the node filesystem
- **Configuration**:
  - `include: /var/log/pods/*/*/*.log` - Collects all pod logs
  - `exclude: /var/log/pods/otel-collector_opentelemetry-collector-daemonset*_*/opentelemetry-collector/*.log` - Excludes collector's own logs
  - `include_file_name: false` - Doesn't include filename in log records
  - `include_file_path: true` - Includes full file path
  - `start_at: end` - Starts reading from end of file (tail mode)
  - `retry_on_failure: enabled: true` - Retries on read failures
  - Uses `container` parser to parse Kubernetes container log format
- **Used in pipeline**: `logs`

#### `hostmetrics`
- **Purpose**: Collects host-level system metrics (CPU, memory, disk, network, filesystem, load)
- **Configuration**:
  - `collection_interval: 30s`
  - `root_path: /hostfs` - Mounts host filesystem at `/hostfs` to access host metrics
  - **Scrapers enabled**:
    - `cpu`: CPU metrics
    - `disk`: Disk I/O metrics
    - `filesystem`: Filesystem usage metrics (with extensive exclusions for system filesystems)
    - `load`: System load average
    - `memory`: Memory usage metrics
    - `network`: Network interface metrics
- **Used in pipeline**: `metrics`

#### `kubeletstats`
- **Purpose**: Collects Kubernetes pod and container metrics from kubelet API
- **Configuration**:
  - `auth_type: serviceAccount` - Uses service account authentication
  - `collection_interval: 20s`
  - `endpoint: ${env:K8S_NODE_IP}:10250` - Kubelet API endpoint
  - `insecure_skip_verify: true` - Skips TLS verification (for development)
  - **Metrics enabled**:
    - `k8s.container.cpu_limit_utilization`
    - `k8s.pod.cpu_limit_utilization`
    - `k8s.pod.cpu_request_utilization`
    - `k8s.pod.memory_limit_utilization`
    - `k8s.pod.memory_request_utilization`
- **Used in pipeline**: `metrics`

### Processors

#### `memory_limiter`
- **Purpose**: Prevents the collector from using excessive memory
- **Configuration**:
  - `check_interval: 5s`
  - `limit_percentage: 80`
  - `spike_limit_percentage: 25`
- **Used in**: All pipelines

#### `batch`
- **Purpose**: Batches telemetry data before exporting
- **Configuration**: Default settings
- **Used in**: All pipelines

#### `cumulativetodelta`
- **Purpose**: Converts cumulative metrics to delta metrics
- **Configuration**: Default settings
- **Used in**: Metrics pipeline (commented out in config, but processor is defined)

#### `k8sattributes`
- **Purpose**: Enriches telemetry with Kubernetes metadata (pod, namespace, deployment, etc.)
- **Configuration**:
  - **Metadata extracted**:
    - `k8s.namespace.name`
    - `k8s.pod.name`
    - `k8s.pod.uid`
    - `k8s.node.name`
    - `k8s.pod.start_time`
    - `k8s.deployment.name`
    - `k8s.replicaset.name`
    - `k8s.replicaset.uid`
    - `k8s.daemonset.name`
    - `k8s.daemonset.uid`
    - `k8s.job.name`
    - `k8s.job.uid`
    - `k8s.container.name`
    - `k8s.cronjob.name`
    - `k8s.statefulset.name`
    - `k8s.statefulset.uid`
    - `container.image.tag`
    - `container.image.name`
    - `k8s.cluster.uid`
  - `otel_annotations: true` - Extracts OpenTelemetry annotations from pods
  - `filter.node_from_env_var: K8S_NODE_NAME` - Only processes pods on this node
  - `passthrough: false` - Doesn't pass through unmatched telemetry
  - **Pod association** (in order):
    1. `k8s.pod.ip` resource attribute
    2. `k8s.pod.uid` resource attribute
    3. Connection metadata
- **Used in**: `logs`, `metrics`, `traces` pipelines

#### `resource/newrelic`
- **Purpose**: Adds New Relic-specific resource attributes
- **Configuration**:
  - Sets `newrelic.entity.type` to `"k8s"`
  - Sets `newrelic.chart.version` to `"0.0.0"`
  - Sets `k8s.cluster.name` from `${env:K8S_CLUSTER_NAME}`
- **Used in**: `logs`, `metrics` pipelines

### Exporters

#### `otlphttp/gateway`
- **Purpose**: Forwards all telemetry to the deployment collector gateway
- **Configuration**:
  - `endpoint: http://opentelemetry-collector-deployment-collector.observability.svc.cluster.local:4318`
- **Used in pipelines**: `logs`, `metrics`, `traces`

#### `otlphttp/newrelic`
- **Purpose**: Direct export to New Relic (backup/fallback, not actively used in pipelines)
- **Configuration**:
  - `endpoint: https://otlp.nr-data.net`
  - `api-key: ${NEW_RELIC_LICENSE_KEY}`
- **Used in pipelines**: None (defined but not used)

#### `debug`
- **Purpose**: Logs telemetry data to collector logs (useful for debugging)
- **Configuration**: Default settings
- **Used in pipelines**: `traces` (logs enabled, others commented out)

### Extensions

#### `health_check`
- **Purpose**: Provides health check endpoint for Kubernetes liveness/readiness probes
- **Configuration**:
  - `endpoint: ${env:MY_POD_IP}:13133`
- **Used in**: Service extensions

### Pipelines

#### Logs Pipeline

**`logs`**: Collects and forwards logs
- Receivers: `otlp`, `filelog`
- Processors: `memory_limiter`, `k8sattributes`, `resource/newrelic`, `batch`
- Exporters: `otlphttp/gateway`

#### Metrics Pipeline

**`metrics`**: Collects and forwards metrics
- Receivers: `otlp`, `hostmetrics`, `kubeletstats`
- Processors: `memory_limiter`, `k8sattributes`, `resource/newrelic`, `batch`
- Exporters: `otlphttp/gateway`

#### Traces Pipeline

**`traces`**: Collects and forwards traces
- Receivers: `otlp`
- Processors: `memory_limiter`, `k8sattributes`, `batch`
- Exporters: `otlphttp/gateway`, `debug`

### Environment Variables

- `MY_POD_IP`: Pod IP address (from `status.podIP`)
- `K8S_NODE_NAME`: Kubernetes node name (from `spec.nodeName`) - Used by k8sattributes processor
- `K8S_NODE_IP`: Kubernetes node IP (from `status.hostIP`) - Used for kubelet API endpoint
- `NEW_RELIC_LICENSE_KEY`: New Relic license key (from secret)
- `K8S_CLUSTER_NAME`: Cluster name (set to `"openshift"`)

### Volume Mounts

The daemonset collector requires access to the host filesystem:

- **`hostfs`**: Mounts host root filesystem at `/hostfs` for hostmetrics receiver
  - `hostPath: /`
  - `mountPath: /hostfs`
  
- **`varlogpods`**: Mounts pod logs directory for filelog receiver
  - `hostPath: /var/log/pods`
  - `mountPath: /var/log/pods`
  - `readOnly: true`

### Security Context

- `runAsUser: 0` - Runs as root (required for host filesystem access)
- `readOnlyRootFilesystem: true` - Root filesystem is read-only
- `allowPrivilegeEscalation: true` - Allows privilege escalation (required for host access)
- `hostNetwork: true` - Uses host network (allows listening on node IP)

## Telemetry Flow

### Application Telemetry Flow

1. **Application** → Sends OTLP to daemonset collector (via node IP)
2. **Daemonset Collector** → Enriches with k8s attributes → Forwards to deployment collector gateway
3. **Deployment Collector** → Routes based on namespace → Exports to tenant-specific New Relic account

### Node-Level Telemetry Flow

1. **Daemonset Collector** → Collects host metrics, kubelet stats, and logs
2. **Daemonset Collector** → Enriches with k8s attributes → Forwards to deployment collector gateway
3. **Deployment Collector** → Routes based on namespace → Exports to New Relic

### Cluster-Level Telemetry Flow

1. **Deployment Collector** → Collects k8s_cluster metrics and k8s_events
2. **Deployment Collector** → Processes and transforms → Exports to New Relic

## Multi-Tenant Routing

The deployment collector implements multi-tenant routing using routing connectors:

1. All telemetry enters through `*_in` pipelines (e.g., `logs/in`, `metrics/in`, `traces/in`)
2. Routing connectors examine the `k8s.namespace.name` resource attribute
3. Telemetry is routed to tenant-specific pipelines:
   - `tenant1-demo` namespace → `*_tenant1` pipelines → `otlphttp/tenant1` exporter
   - `tenant2-demo` namespace → `*_tenant2` pipelines → `otlphttp/tenant2` exporter
   - Other namespaces → Default pipelines → `otlphttp/newrelic` exporter

This ensures that each tenant's telemetry is exported to their own New Relic account using their own license key.

## References

- [OpenTelemetry Collector Documentation](https://opentelemetry.io/docs/collector/)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [New Relic OTLP Endpoint](https://docs.newrelic.com/docs/more-integrations/open-source-telemetry-integrations/opentelemetry/opentelemetry-setup/)
