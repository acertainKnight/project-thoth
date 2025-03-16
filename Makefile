SHELL := /bin/bash
PROJECT_NAME := $(shell grep "name" pyproject.toml | head -1 | cut -d'"' -f2 || echo "default_project")
SERVICE_NAME := app
TAG ?= latest

# Colors for better output
ccend := $(shell echo -e '\033[0m')
ccbold := $(shell echo -e '\033[1m')
ccgreen := $(shell echo -e '\033[32m')
ccred := $(shell echo -e '\033[31m')
ccso := $(shell echo -e '\033[7m')

# Help formatting
HELP_SECTION_COLOR := $(ccbold)
HELP_COMMAND_COLOR := $(ccgreen)
HELP_TEXT_COLOR := $(ccend)

# Environment checks
DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "$(DOCKER_COMPOSE)")
DOCKER_BASE_IMAGE := $(shell scripts/utilities/get_docker_base.sh false)
# Docker status check function
define check_docker_running
	docker ps >/dev/null && echo "true" || echo "false"
endef

# Environment variables check
REQUIRED_ENV_VARS := TRINO_USER TRINO_PW_DEV RUN_ENV DATA_ENV

$(shell find ./scripts -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true)

PYTHON_VERSION := $(shell scripts/utilities/get_python_version.sh)

# Export variables for docker-compose
export PROJECT_NAME
export TAG
export PYTHON_VERSION

# Add to the variables section
BUILD_FLAGS := $(filter-out $@,$(MAKECMDGOALS))

# Load environment variables from .env file if it exists
-include .env
export $(shell sed 's/=.*//' .env 2>/dev/null)

####################### Environment Setup
.PHONY: check-env
check-env:
	@echo "$(ccso)--> Checking environment variables $(ccend)"
	@for var in $(REQUIRED_ENV_VARS); do \
		if [ -z "$${!var}" ]; then \
			echo "$(ccred)Error: $$var is not set. Please set it in .env file or environment$(ccend)"; \
			exit 1; \
		fi \
	done

.PHONY: validate-python
validate-python:
	@echo "$(ccso)--> Checking Python version (required: $(PYTHON_VERSION)) $(ccend)"

.PHONY: validate-docker
validate-docker:
	@echo "$(ccso)--> Checking Docker installation $(ccend)"
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "$(ccred)Error: Docker is not installed$(ccend)"; \
		exit 1; \
	fi
	@if ! docker info >/dev/null 2>&1; then \
		echo "$(ccred)Error: Docker daemon is not running$(ccend)"; \
		exit 1; \
	fi

####################### Build Variants
.PHONY: build

build: check-env
	@echo "$(ccso)--> Processing build arguments$(ccend)"
	$(eval EXTRAS := $(shell scripts/utilities/process_build_args.sh $(BUILD_FLAGS)))
	$(eval USE_CUDA := $(shell echo "$(BUILD_FLAGS)" | grep -q "gpu" && echo "true" || echo "false"))
	$(eval USE_CACHE := $(shell echo "$(BUILD_FLAGS)" | grep -q "no-cache" && echo "--no-cache" || echo ""))
	$(eval DOCKER_BASE := $(shell scripts/utilities/get_docker_base.sh $(USE_CUDA)))
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	$(eval BUILD_PROFILE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "gpu-build"; else echo "build"; fi))
	@echo "$(ccso)--> Clearing old cache (maintaining most recent)$(ccend)"
	@if [ "$(USE_CUDA)" = "true" ]; then \
		export CUDA_VERSION=$$(scripts/utilities/get_cuda_config.sh version); \
		export CUDNN_VERSION=$$(scripts/utilities/get_cuda_config.sh cudnn); \
		export NCCL_VERSION=$$(scripts/utilities/get_cuda_config.sh nccl); \
	fi
	@echo "$(ccso)--> Building Docker image (Python $(PYTHON_VERSION)) with extras: $(EXTRAS) $(USE_CACHE)$(ccend)"
	INSTALL_EXTRAS="$(EXTRAS)" DOCKER_BASE_IMAGE="$(DOCKER_BASE)" $(DOCKER_COMPOSE) --profile $(BUILD_PROFILE) build --pull $(USE_CACHE) $(BUILD_SERVICE)
	@if [ ! -z "$(TAG)" ]; then \
		docker tag $(PROJECT_NAME):latest $(PROJECT_NAME):$(TAG); \
	fi

####################### Docker Operations
.PHONY: start stop clean

start: check-env ## Start Docker services if not already running
	@if [ "$$($(call check_docker_running))" = "true" ]; then \
		echo "$(ccgreen)Services already running$(ccend)"; \
	else \
		echo "$(ccso)--> Starting services $(ccend)"; \
		$(eval USE_CUDA := $(shell echo "$(BUILD_FLAGS)" | grep -q "gpu" && echo "true" || echo "false")) \
		if [ "$(USE_CUDA)" = "true" ]; then \
			$(DOCKER_COMPOSE) --profile gpu up -d; \
		else \
			$(DOCKER_COMPOSE) --profile default up -d; \
		fi; \
		echo "$(ccgreen)Waiting for services to be healthy...$(ccend)"; \
	fi

stop: ## Stop Docker services
	@if [ "$$($(call check_docker_running))" = "true" ]; then \
		echo "$(ccso)--> Stopping services $(ccend)"; \
		$(DOCKER_COMPOSE) down; \
	else \
		echo "$(ccgreen)No services running$(ccend)"; \
	fi

clean: stop ## Remove all Docker resources and cached files
	@echo "$(ccso)--> Cleaning up Docker resources $(ccend)"
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -f
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

####################### Development Tasks
.PHONY: develop shell jupyter lab precommit autoformat migrate test lint check

develop: check-env ## Start development environment or attach to existing container
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@if [ "$$($(call check_docker_running))" = "false" ]; then \
		echo "$(ccso)--> Starting development environment$(ccend)"; \
		$(MAKE) start; \
	fi
	@echo "$(ccso)--> Attaching to development container$(ccend)"
	$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) bash

shell: develop ## Alias for develop command

jupyter: lab ## Alias for lab command

lab: ## Starts a container running a jupyter lab
	@echo "$(ccso)--> Starting Jupyter Lab$(ccend)"
	@$(DOCKER_COMPOSE) kill lab && $(DOCKER_COMPOSE) rm -f lab || true
	$(DOCKER_COMPOSE) run --service-ports --rm lab

autoformat: ## Auto format all python files
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@echo "$(ccso)--> Auto-formatting Python files$(ccend)"
	$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pre-commit run black --all-files
	$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pre-commit run ruff --all-files

precommit: ## Run pre-commit check on all files
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@echo "$(ccso)--> Running pre-commit checks$(ccend)"
	$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pre-commit run --all-files

migrate: ## Run migrations (add add-noqa=true to add #noqa to all failing lines)
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@echo "$(ccso)--> Running migrations$(ccend)"
	@if [ "$(add-noqa)" = "true" ]; then \
		echo "Adding #noqa annotations..."; \
		$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pre-commit run --all-files; \
		$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) ruff check --add-noqa; \
	else \
		$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pre-commit run --all-files; \
	fi

test: ## Run tests with optional arguments: make test ARGS="-v -k test_name"
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@echo "$(ccso)--> Running tests $(ccend)"
	$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pytest tests/ $(ARGS)

lint: ## Run code quality checks
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@echo "$(ccso)--> Running linters $(ccend)"
	$(DOCKER_COMPOSE) run --service-ports --rm $(BUILD_SERVICE) pre-commit run --all-files

check: lint test ## Run all checks (linting and tests)
	$(eval BUILD_SERVICE := $(shell if [ "$(USE_CUDA)" = "true" ]; then echo "app-build-gpu"; else echo "app-build"; fi))
	@echo "$(ccso)--> All checks completed $(ccend)"

####################### Utility Commands
.PHONY: logs ps git

logs: ## View Docker container logs
	$(DOCKER_COMPOSE) logs -f $(BUILD_SERVICE)

ps: ## List running Docker containers
	$(DOCKER_COMPOSE) ps

git: ## Git command to run from within Docker
	$(DOCKER_COMPOSE) exec app git $(filter-out $@,$(MAKECMDGOALS))

%:
	@:

####################### Help Documentation
help: ## Display this help message
	@echo '$(ccgreen)Fedspeak Sentiment Analysis Development Commands$(ccend)'
	@echo ''
	@echo '$(ccbold)Initial Setup:$(ccend)'
	@echo '  1. Ensure required environment variables are set'
	@echo '  2. Run make build        # Builds with latest tag'
	@echo '  3. Run make build TAG=v1.0.0  # Builds with specific tag'
	@echo ''
	@echo '$(ccbold)Build Options:$(ccend)'
	@echo '  make build              # Basic build'
	@echo '  make build dev        # Development build'
	@echo '  make build lab        # Jupyter Lab build'
	@echo '  make build gpu        # GPU-enabled build'
	@echo '  make build no-cache   # Build without using cache'
	@echo ''
	@echo '$(ccbold)Build Flag Combinations:$(ccend)'
	@echo '  make build dev lab  # Development build with Jupyter'
	@echo '  make build dev gpu  # Development build with GPU support'
	@echo '  make build dev lab gpu  # Full development environment'
	@echo '  make build dev no-cache   # Fresh development build'
	@echo ''
	@echo '$(ccbold)Custom Extras:$(ccend)'
	@echo '  Any extra defined in dependencies/*.txt can be used as a flag:'
	@echo '  make build custom-extra     # Build with custom-extra.txt dependencies'
	@echo '  make build dev custom-extra  # Combine with other flags'
	@echo ''
	@echo '$(ccbold)Development Workflow:$(ccend)'
	@echo '  1. Run make develop      # Start development shell'
	@echo '  2. Run make autoformat   # Format code'
	@echo '  3. Run make precommit    # Run pre-commit checks'
	@echo '  4. Run make check        # Run all checks'
	@echo ''
	@echo '$(ccbold)Jupyter Lab:$(ccend)'
	@echo '  - Run make lab           # Start Jupyter Lab'
	@echo ''
	@echo '$(ccbold)Migration (to be used when migrating an existing repo):$(ccend)'
	@echo '  - Run make migrate                  # Run normal migration'
	@echo '  - Run make migrate add-noqa=true    # Add #noqa to failing lines'
	@echo ''
	@echo '$(ccbold)Testing:$(ccend)'
	@echo '  - Run make test          # Run all tests'
	@echo '  - Run make test ARGS="-v" # Run tests with specific arguments'
	@echo ''
	@echo '$(ccbold)Cleanup:$(ccend)'
	@echo '  1. Run make stop to stop services'
	@echo '  2. Run make clean for full cleanup'
	@echo ''
	@awk '{\
		if ($$0 ~ /^#######################/) { \
			section_name = substr($$0, 25, length($$0)-25); \
			printf "\n$(HELP_SECTION_COLOR)%s:$(HELP_TEXT_COLOR)\n", section_name; \
		} \
		else if ($$0 ~ /^[a-zA-Z0-9_-]+:.*?## .*$$/) { \
			command = $$1; \
			gsub(/:/, "", command); \
			description = $$0; \
			gsub(/^[^#]*## /, "", description); \
			printf "  $(HELP_COMMAND_COLOR)%-20s$(HELP_TEXT_COLOR) %s\n", command, description; \
		} \
	}' $(MAKEFILE_LIST)
	@echo ''
	@echo '$(ccbold)Note:$(ccend) All commands run inside Docker containers for consistency'
