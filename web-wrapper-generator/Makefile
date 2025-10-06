.PHONY: build run clean test docker-build docker-run docker-stop help

# Variables
BINARY_NAME=web-wrapper-generator
PORT?=8080

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

build: ## Build the Go binary
	@echo "Building $(BINARY_NAME)..."
	go build -o $(BINARY_NAME) .
	@echo "Build complete!"

run: build ## Build and run the application
	@echo "Starting server on port $(PORT)..."
	PORT=$(PORT) ./$(BINARY_NAME)

clean: ## Clean build artifacts
	@echo "Cleaning..."
	rm -f $(BINARY_NAME)
	rm -rf builds/*/
	@echo "Clean complete!"

test: ## Run tests
	go test -v ./...

docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker-compose build
	@echo "Docker build complete!"

docker-run: ## Run with Docker Compose
	@echo "Starting with Docker Compose..."
	docker-compose up -d
	@echo "Server running at http://localhost:$(PORT)"

docker-stop: ## Stop Docker Compose
	@echo "Stopping Docker Compose..."
	docker-compose down
	@echo "Stopped!"

docker-logs: ## Show Docker logs
	docker-compose logs -f

install-deps: ## Install Go dependencies
	go mod download
	go mod tidy

fmt: ## Format Go code
	go fmt ./...

vet: ## Run go vet
	go vet ./...

lint: fmt vet ## Run linters

dev: ## Run in development mode
	@echo "Running in development mode..."
	@echo "Server will restart on code changes (requires 'air' or similar)"
	PORT=$(PORT) go run .

.DEFAULT_GOAL := help
