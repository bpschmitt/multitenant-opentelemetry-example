.PHONY: help build build-sender build-receiver build-loadgen build-local build-local-sender build-local-receiver build-local-loadgen push push-sender push-receiver push-loadgen setup-buildx deploy-tenant1 deploy-tenant2 undeploy-tenant1 undeploy-tenant2 test clean

# Configuration
REGISTRY ?= demo-app
TAG ?= latest
PLATFORMS ?= linux/amd64,linux/arm64
HELM_CHART = ./helm/demo-app
NAMESPACE_TENANT1 = tenant1-demo
NAMESPACE_TENANT2 = tenant2-demo
OTLP_ENDPOINT = http://opentelemetry-collector.otel-collector.svc.cluster.local:4317
BUILDX_BUILDER = multiarch-builder
# Set PUSH=false to build without pushing (images will be in buildx cache only)
PUSH ?= true
# Image registry for Helm deployments (if set, uses global.imageRegistry in Helm)
# Example: IMAGE_REGISTRY=docker.io/myorg or IMAGE_REGISTRY=ghcr.io/myorg
IMAGE_REGISTRY ?=

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup-buildx: ## Set up Docker buildx for multi-platform builds
	@echo "Setting up Docker buildx..."
	@if ! docker buildx ls | grep -q $(BUILDX_BUILDER); then \
		docker buildx create --name $(BUILDX_BUILDER) --driver docker-container --use || true; \
		docker buildx inspect --bootstrap || true; \
	fi
	@docker buildx use $(BUILDX_BUILDER)

build: setup-buildx build-sender build-receiver build-loadgen ## Build all Docker images (multi-platform: amd64, arm64)

build-sender: setup-buildx ## Build sender service Docker image (multi-platform: amd64, arm64)
	@echo "Building sender service for platforms: $(PLATFORMS)..."
	@if [ "$(PUSH)" = "true" ]; then \
		echo "Building and pushing sender service..."; \
		docker buildx build \
			--platform $(PLATFORMS) \
			-t $(REGISTRY)/sender:$(TAG) \
			--push \
			./sender; \
	else \
		echo "Building sender service (to cache only, not pushing - set PUSH=true to push)..."; \
		docker buildx build \
			--platform $(PLATFORMS) \
			-t $(REGISTRY)/sender:$(TAG) \
			./sender; \
	fi

build-receiver: setup-buildx ## Build receiver service Docker image (multi-platform: amd64, arm64)
	@echo "Building receiver service for platforms: $(PLATFORMS)..."
	@if [ "$(PUSH)" = "true" ]; then \
		echo "Building and pushing receiver service..."; \
		docker buildx build \
			--platform $(PLATFORMS) \
			-t $(REGISTRY)/receiver:$(TAG) \
			--push \
			./receiver; \
	else \
		echo "Building receiver service (to cache only, not pushing - set PUSH=true to push)..."; \
		docker buildx build \
			--platform $(PLATFORMS) \
			-t $(REGISTRY)/receiver:$(TAG) \
			./receiver; \
	fi

build-loadgen: setup-buildx ## Build loadgen service Docker image (multi-platform: amd64, arm64)
	@echo "Building loadgen service for platforms: $(PLATFORMS)..."
	@if [ "$(PUSH)" = "true" ]; then \
		echo "Building and pushing loadgen service..."; \
		docker buildx build \
			--platform $(PLATFORMS) \
			-t $(REGISTRY)/loadgen:$(TAG) \
			--push \
			./loadgen; \
	else \
		echo "Building loadgen service (to cache only, not pushing - set PUSH=true to push)..."; \
		docker buildx build \
			--platform $(PLATFORMS) \
			-t $(REGISTRY)/loadgen:$(TAG) \
			./loadgen; \
	fi

build-local: build-local-sender build-local-receiver build-local-loadgen ## Build all Docker images for local use (single platform)

build-local-sender: ## Build sender service Docker image for local use (single platform)
	@echo "Building sender service for local use..."
	docker build -t $(REGISTRY)/sender:$(TAG) ./sender

build-local-receiver: ## Build receiver service Docker image for local use (single platform)
	@echo "Building receiver service for local use..."
	docker build -t $(REGISTRY)/receiver:$(TAG) ./receiver

build-local-loadgen: ## Build loadgen service Docker image for local use (single platform)
	@echo "Building loadgen service for local use..."
	docker build -t $(REGISTRY)/loadgen:$(TAG) ./loadgen

push: push-sender push-receiver push-loadgen ## Push all Docker images (rebuilds and pushes)

push-sender: setup-buildx ## Push sender service Docker image (multi-platform)
	@echo "Building and pushing sender service for platforms: $(PLATFORMS)..."
	docker buildx build \
		--platform $(PLATFORMS) \
		-t $(REGISTRY)/sender:$(TAG) \
		--push \
		./sender

push-receiver: setup-buildx ## Push receiver service Docker image (multi-platform)
	@echo "Building and pushing receiver service for platforms: $(PLATFORMS)..."
	docker buildx build \
		--platform $(PLATFORMS) \
		-t $(REGISTRY)/receiver:$(TAG) \
		--push \
		./receiver

push-loadgen: setup-buildx ## Push loadgen service Docker image (multi-platform)
	@echo "Building and pushing loadgen service for platforms: $(PLATFORMS)..."
	docker buildx build \
		--platform $(PLATFORMS) \
		-t $(REGISTRY)/loadgen:$(TAG) \
		--push \
		./loadgen

deploy-tenant1: ## Deploy tenant 1 to Kubernetes
	@echo "Deploying tenant 1..."
	@kubectl create namespace $(NAMESPACE_TENANT1) --dry-run=client -o yaml | kubectl apply -f -
	@if [ -n "$(IMAGE_REGISTRY)" ]; then \
		helm upgrade --install demo-app-tenant1 $(HELM_CHART) \
			--namespace $(NAMESPACE_TENANT1) \
			--values $(HELM_CHART)/values-tenant1.yaml \
			--set global.otlpEndpoint=$(OTLP_ENDPOINT) \
			--set global.imageRegistry=$(IMAGE_REGISTRY) \
			--set sender.image.repository=sender \
			--set sender.image.tag=$(TAG) \
			--set receiver.image.repository=receiver \
			--set receiver.image.tag=$(TAG); \
	else \
		helm upgrade --install demo-app-tenant1 $(HELM_CHART) \
			--namespace $(NAMESPACE_TENANT1) \
			--values $(HELM_CHART)/values-tenant1.yaml \
			--set global.otlpEndpoint=$(OTLP_ENDPOINT) \
			--set sender.image.repository=$(REGISTRY)/sender \
			--set sender.image.tag=$(TAG) \
			--set receiver.image.repository=$(REGISTRY)/receiver \
			--set receiver.image.tag=$(TAG); \
	fi

deploy-tenant2: ## Deploy tenant 2 to Kubernetes
	@echo "Deploying tenant 2..."
	@kubectl create namespace $(NAMESPACE_TENANT2) --dry-run=client -o yaml | kubectl apply -f -
	@if [ -n "$(IMAGE_REGISTRY)" ]; then \
		helm upgrade --install demo-app-tenant2 $(HELM_CHART) \
			--namespace $(NAMESPACE_TENANT2) \
			--values $(HELM_CHART)/values-tenant2.yaml \
			--set global.otlpEndpoint=$(OTLP_ENDPOINT) \
			--set global.imageRegistry=$(IMAGE_REGISTRY) \
			--set sender.image.repository=sender \
			--set sender.image.tag=$(TAG) \
			--set receiver.image.repository=receiver \
			--set receiver.image.tag=$(TAG); \
	else \
		helm upgrade --install demo-app-tenant2 $(HELM_CHART) \
			--namespace $(NAMESPACE_TENANT2) \
			--values $(HELM_CHART)/values-tenant2.yaml \
			--set global.otlpEndpoint=$(OTLP_ENDPOINT) \
			--set sender.image.repository=$(REGISTRY)/sender \
			--set sender.image.tag=$(TAG) \
			--set receiver.image.repository=$(REGISTRY)/receiver \
			--set receiver.image.tag=$(TAG); \
	fi

deploy-all: deploy-tenant1 deploy-tenant2 ## Deploy both tenants

undeploy-tenant1: ## Uninstall tenant 1
	@echo "Uninstalling tenant 1..."
	helm uninstall demo-app-tenant1 --namespace $(NAMESPACE_TENANT1) || true
	@kubectl delete namespace $(NAMESPACE_TENANT1) || true

undeploy-tenant2: ## Uninstall tenant 2
	@echo "Uninstalling tenant 2..."
	helm uninstall demo-app-tenant2 --namespace $(NAMESPACE_TENANT2) || true
	@kubectl delete namespace $(NAMESPACE_TENANT2) || true

undeploy-all: undeploy-tenant1 undeploy-tenant2 ## Uninstall both tenants

status-tenant1: ## Show status of tenant 1
	@echo "=== Tenant 1 Status ==="
	@kubectl get pods -n $(NAMESPACE_TENANT1)
	@echo ""
	@kubectl get svc -n $(NAMESPACE_TENANT1)

status-tenant2: ## Show status of tenant 2
	@echo "=== Tenant 2 Status ==="
	@kubectl get pods -n $(NAMESPACE_TENANT2)
	@echo ""
	@kubectl get svc -n $(NAMESPACE_TENANT2)

status: status-tenant1 status-tenant2 ## Show status of all tenants

logs-sender-tenant1: ## Show logs from sender service (tenant 1)
	kubectl logs -n $(NAMESPACE_TENANT1) -l app=sender --tail=50 -f

logs-receiver-tenant1: ## Show logs from receiver service (tenant 1)
	kubectl logs -n $(NAMESPACE_TENANT1) -l app=receiver --tail=50 -f

logs-sender-tenant2: ## Show logs from sender service (tenant 2)
	kubectl logs -n $(NAMESPACE_TENANT2) -l app=sender --tail=50 -f

logs-receiver-tenant2: ## Show logs from receiver service (tenant 2)
	kubectl logs -n $(NAMESPACE_TENANT2) -l app=receiver --tail=50 -f

port-forward-tenant1: ## Port-forward sender service (tenant 1) to localhost:8000
	kubectl port-forward -n $(NAMESPACE_TENANT1) svc/sender 8000:8000

port-forward-tenant2: ## Port-forward sender service (tenant 2) to localhost:8000
	kubectl port-forward -n $(NAMESPACE_TENANT2) svc/sender 8000:8000

test-tenant1: ## Send a test request to tenant 1 (requires port-forward)
	@echo "Sending test request to tenant 1..."
	@curl -X POST http://localhost:8000/send \
		-H "Content-Type: application/json" \
		-d '{"request_id": "test-$(shell date +%s)", "message": "Hello from Makefile"}'

test-tenant2: ## Send a test request to tenant 2 (requires port-forward)
	@echo "Sending test request to tenant 2..."
	@curl -X POST http://localhost:8000/send \
		-H "Content-Type: application/json" \
		-d '{"request_id": "test-$(shell date +%s)", "message": "Hello from Makefile"}'

clean: ## Clean up local Docker images
	@echo "Cleaning up Docker images..."
	docker rmi $(REGISTRY)/sender:$(TAG) || true
	docker rmi $(REGISTRY)/receiver:$(TAG) || true
	docker rmi $(REGISTRY)/loadgen:$(TAG) || true

