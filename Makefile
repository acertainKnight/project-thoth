# =============================================================================
# Thoth Project Makefile
# =============================================================================
# This Makefile provides convenient commands to build the Obsidian extension,
# deploy it to your Obsidian vault's plugins directory, and start the Thoth API.

# -----------------------------------------------------------------------------
# Configuration Variables
# -----------------------------------------------------------------------------

# Default Obsidian vault path (can be overridden)
# Common locations:
# - Linux/WSL: /mnt/c/Users/$(USER)/Documents/Obsidian Vault
# - macOS: /Users/$(USER)/Documents/Obsidian Vault
# - Windows: C:/Users/$(USER)/Documents/Obsidian Vault
OBSIDIAN_VAULT ?= /mnt/c/Users/nghal/Documents/Obsidian Vault

# Plugin directories
PLUGIN_SRC_DIR = obsidian-plugin/thoth-obsidian
PLUGIN_DEST_DIR = $(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian

# API Server configuration
API_HOST ?= 0.0.0.0
API_PORT ?= 8000
API_RELOAD ?= false

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

# -----------------------------------------------------------------------------
# Help Target (Default)
# -----------------------------------------------------------------------------

.PHONY: help
help: ## Show this help message
	@echo "$(GREEN)Thoth Project - Available Commands$(NC)"
	@echo "========================================"
	@echo ""
	@echo "$(YELLOW)Quick Start:$(NC)"
	@echo "  make deploy-plugin    # Build and deploy Obsidian extension"
	@echo "  make start-api        # Start the Thoth API server"
	@echo "  make dev              # Start both plugin build watcher and API"
	@echo ""
	@echo "$(YELLOW)Available targets:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)Configuration:$(NC)"
	@echo "  OBSIDIAN_VAULT=$(OBSIDIAN_VAULT)"
	@echo "  API_HOST=$(API_HOST)"
	@echo "  API_PORT=$(API_PORT)"
	@echo ""
	@echo "$(YELLOW)Override example:$(NC)"
	@echo '  make deploy-plugin OBSIDIAN_VAULT="/path/to/your/vault"'

# -----------------------------------------------------------------------------
# Obsidian Plugin Targets
# -----------------------------------------------------------------------------

.PHONY: check-obsidian-vault
check-obsidian-vault: ## Check if Obsidian vault path exists
	@echo "$(YELLOW)Checking Obsidian vault path...$(NC)"
	@if [ ! -d "$(OBSIDIAN_VAULT)" ]; then \
		echo "$(RED)Error: Obsidian vault not found at: $(OBSIDIAN_VAULT)$(NC)"; \
		echo "$(YELLOW)Set the correct path with: make deploy-plugin OBSIDIAN_VAULT=\"/your/vault/path\"$(NC)"; \
		echo "$(YELLOW)Common locations:$(NC)"; \
		echo "  - Linux/WSL: /mnt/c/Users/\$$USER/Documents/Obsidian Vault"; \
		echo "  - macOS: /Users/\$$USER/Documents/Obsidian Vault"; \
		echo "  - Custom: /path/to/your/obsidian/vault"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Obsidian vault found at: $(OBSIDIAN_VAULT)$(NC)"

.PHONY: install-plugin-deps
install-plugin-deps: ## Install Obsidian plugin dependencies
	@echo "$(YELLOW)Installing plugin dependencies...$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm install
	@echo "$(GREEN)✓ Plugin dependencies installed$(NC)"

.PHONY: build-plugin
build-plugin: install-plugin-deps ## Build the Obsidian plugin
	@echo "$(YELLOW)Building Obsidian plugin...$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm run build
	@echo "$(GREEN)✓ Plugin built successfully$(NC)"

.PHONY: clean-plugin
clean-plugin: ## Clean plugin build artifacts
	@echo "$(YELLOW)Cleaning plugin build artifacts...$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm run clean || true
	@rm -rf $(PLUGIN_SRC_DIR)/dist
	@echo "$(GREEN)✓ Plugin cleaned$(NC)"

.PHONY: deploy-plugin
deploy-plugin: check-obsidian-vault build-plugin ## Build and deploy plugin to Obsidian vault
	@echo "$(YELLOW)Deploying plugin to Obsidian vault...$(NC)"
	@mkdir -p "$(PLUGIN_DEST_DIR)"
	@cp -r $(PLUGIN_SRC_DIR)/dist/* "$(PLUGIN_DEST_DIR)/"
	@cp $(PLUGIN_SRC_DIR)/manifest.json "$(PLUGIN_DEST_DIR)/"
	@cp $(PLUGIN_SRC_DIR)/styles.css "$(PLUGIN_DEST_DIR)/" 2>/dev/null || true
	@echo "$(GREEN)✓ Plugin deployed to: $(PLUGIN_DEST_DIR)$(NC)"
	@echo "$(YELLOW)Remember to reload the plugin in Obsidian: Ctrl/Cmd+P → 'Reload app'$(NC)"

.PHONY: watch-plugin
watch-plugin: install-plugin-deps ## Watch plugin source for changes and rebuild
	@echo "$(YELLOW)Starting plugin watch mode...$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm run watch

# -----------------------------------------------------------------------------
# API Server Targets
# -----------------------------------------------------------------------------

.PHONY: check-venv
check-venv: ## Check if virtual environment is activated
	@echo "$(YELLOW)Checking Python environment...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		echo "$(GREEN)✓ Using uv package manager$(NC)"; \
	elif [ -n "$$VIRTUAL_ENV" ]; then \
		echo "$(GREEN)✓ Virtual environment active: $$VIRTUAL_ENV$(NC)"; \
	elif [ -d .venv ]; then \
		echo "$(YELLOW)Virtual environment found but not activated$(NC)"; \
		echo "$(YELLOW)Run: source .venv/bin/activate$(NC)"; \
	else \
		echo "$(RED)Warning: No virtual environment detected$(NC)"; \
		echo "$(YELLOW)Consider creating one: python -m venv .venv$(NC)"; \
	fi

.PHONY: start-api
start-api: check-venv ## Start the Thoth API server
	@echo "$(YELLOW)Starting Thoth API server on $(API_HOST):$(API_PORT)...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		uv run python -m thoth api --host $(API_HOST) --port $(API_PORT); \
	elif [ -d .venv ]; then \
		source .venv/bin/activate && python -m thoth api --host $(API_HOST) --port $(API_PORT); \
	else \
		python -m thoth api --host $(API_HOST) --port $(API_PORT); \
	fi

.PHONY: start-api-dev
start-api-dev: check-venv ## Start API server in development mode with auto-reload
	@echo "$(YELLOW)Starting Thoth API server in development mode...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		uv run python -m thoth api --host $(API_HOST) --port $(API_PORT) --reload; \
	elif [ -d .venv ]; then \
		source .venv/bin/activate && python -m thoth api --host $(API_HOST) --port $(API_PORT) --reload; \
	else \
		python -m thoth api --host $(API_HOST) --port $(API_PORT) --reload; \
	fi

.PHONY: stop-api
stop-api: ## Stop the Thoth API server
	@echo "$(YELLOW)Stopping Thoth API server...$(NC)"
	@pkill -f "python -m thoth api" || echo "$(YELLOW)No API server process found$(NC)"
	@echo "$(GREEN)✓ API server stopped$(NC)"

# -----------------------------------------------------------------------------
# Development Targets
# -----------------------------------------------------------------------------

.PHONY: dev
dev: ## Start development mode (plugin watcher + API server)
	@echo "$(YELLOW)Starting development mode...$(NC)"
	@echo "$(YELLOW)This will start both the plugin watcher and API server$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop both processes$(NC)"
	@trap 'kill %1 %2 2>/dev/null || true' INT; \
	make watch-plugin & \
	sleep 2 && make start-api-dev & \
	wait

.PHONY: full-deploy
full-deploy: deploy-plugin start-api ## Deploy plugin and start API server
	@echo "$(GREEN)✓ Full deployment complete!$(NC)"
	@echo "$(YELLOW)Plugin deployed to Obsidian vault$(NC)"
	@echo "$(YELLOW)API server running on http://$(API_HOST):$(API_PORT)$(NC)"

# -----------------------------------------------------------------------------
# Utility Targets
# -----------------------------------------------------------------------------

.PHONY: check-deps
check-deps: ## Check if required dependencies are installed
	@echo "$(YELLOW)Checking dependencies...$(NC)"
	@echo -n "Node.js: "
	@if command -v node >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $$(node --version)$(NC)"; \
	else \
		echo "$(RED)✗ Not found$(NC)"; \
	fi
	@echo -n "npm: "
	@if command -v npm >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $$(npm --version)$(NC)"; \
	else \
		echo "$(RED)✗ Not found$(NC)"; \
	fi
	@echo -n "Python: "
	@if command -v python >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $$(python --version)$(NC)"; \
	elif command -v python3 >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $$(python3 --version)$(NC)"; \
	else \
		echo "$(RED)✗ Not found$(NC)"; \
	fi
	@echo -n "uv: "
	@if command -v uv >/dev/null 2>&1; then \
		echo "$(GREEN)✓ $$(uv --version)$(NC)"; \
	else \
		echo "$(YELLOW)○ Not found (optional)$(NC)"; \
	fi

.PHONY: clean
clean: clean-plugin ## Clean all build artifacts
	@echo "$(YELLOW)Cleaning all build artifacts...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ All artifacts cleaned$(NC)"

.PHONY: status
status: ## Show current status of services
	@echo "$(YELLOW)Service Status:$(NC)"
	@echo "==============="
	@echo -n "API Server: "
	@if pgrep -f "python -m thoth api" >/dev/null; then \
		echo "$(GREEN)✓ Running$(NC)"; \
	else \
		echo "$(RED)✗ Stopped$(NC)"; \
	fi
	@echo -n "Plugin Build: "
	@if [ -f "$(PLUGIN_SRC_DIR)/dist/main.js" ]; then \
		echo "$(GREEN)✓ Built$(NC)"; \
	else \
		echo "$(YELLOW)○ Not built$(NC)"; \
	fi
	@echo -n "Plugin Deployed: "
	@if [ -f "$(PLUGIN_DEST_DIR)/main.js" ]; then \
		echo "$(GREEN)✓ Deployed$(NC)"; \
	else \
		echo "$(YELLOW)○ Not deployed$(NC)"; \
	fi

.PHONY: logs
logs: ## Show API server logs (if running)
	@echo "$(YELLOW)Showing API server logs...$(NC)"
	@tail -f logs/thoth.log 2>/dev/null || echo "$(YELLOW)No logs found. Make sure the API server is running.$(NC)"

# -----------------------------------------------------------------------------
# Docker Targets
# -----------------------------------------------------------------------------

.PHONY: docker-build
docker-build: ## Build Docker images
	@echo "$(YELLOW)Building Docker images...$(NC)"
	@docker build -t thoth-app:latest -f Dockerfile .
	@docker build -t thoth-app:dev -f Dockerfile.dev .
	@echo "$(GREEN)✓ Docker images built$(NC)"

.PHONY: docker-build-prod
docker-build-prod: ## Build production Docker image
	@echo "$(YELLOW)Building production Docker image...$(NC)"
	@docker build -t thoth-app:latest --target runtime -f Dockerfile .
	@echo "$(GREEN)✓ Production Docker image built$(NC)"

.PHONY: docker-build-dev
docker-build-dev: ## Build development Docker image
	@echo "$(YELLOW)Building development Docker image...$(NC)"
	@docker build -t thoth-app:dev -f Dockerfile.dev .
	@echo "$(GREEN)✓ Development Docker image built$(NC)"

.PHONY: docker-up
docker-up: ## Start Docker services (production)
	@echo "$(YELLOW)Starting Docker services...$(NC)"
	@docker compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)API server: http://localhost:8000$(NC)"
	@echo "$(YELLOW)MCP server: http://localhost:8001$(NC)"
	@echo "$(YELLOW)ChromaDB: http://localhost:8003$(NC)"
	@echo "$(YELLOW)Letta server: http://localhost:8283$(NC)"

.PHONY: docker-up-dev
docker-up-dev: ## Start Docker services (development)
	@echo "$(YELLOW)Starting Docker development services...$(NC)"
	@docker compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Development services started$(NC)"
	@echo "$(YELLOW)API server: http://localhost:8000$(NC)"
	@echo "$(YELLOW)MCP server: http://localhost:8001$(NC)"
	@echo "$(YELLOW)ChromaDB: http://localhost:8003$(NC)"
	@echo "$(YELLOW)Letta server: http://localhost:8283$(NC)"

.PHONY: docker-up-prod
docker-up-prod: ## Start Docker services (production)
	@echo "$(YELLOW)Starting Docker production services...$(NC)"
	@docker compose -f docker-compose.prod.yml up -d
	@echo "$(GREEN)✓ Production services started$(NC)"

.PHONY: docker-down
docker-down: ## Stop Docker services
	@echo "$(YELLOW)Stopping Docker services...$(NC)"
	@docker compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

.PHONY: docker-down-dev
docker-down-dev: ## Stop Docker development services
	@echo "$(YELLOW)Stopping Docker development services...$(NC)"
	@docker compose -f docker-compose.dev.yml down
	@echo "$(GREEN)✓ Development services stopped$(NC)"

.PHONY: docker-down-prod
docker-down-prod: ## Stop Docker production services
	@echo "$(YELLOW)Stopping Docker production services...$(NC)"
	@docker compose -f docker-compose.prod.yml down
	@echo "$(GREEN)✓ Production services stopped$(NC)"

.PHONY: docker-logs
docker-logs: ## Show Docker service logs
	@echo "$(YELLOW)Showing Docker service logs...$(NC)"
	@docker compose logs -f

.PHONY: docker-logs-dev
docker-logs-dev: ## Show Docker development service logs
	@echo "$(YELLOW)Showing Docker development service logs...$(NC)"
	@docker compose -f docker-compose.dev.yml logs -f

.PHONY: docker-logs-app
docker-logs-app: ## Show main application logs
	@echo "$(YELLOW)Showing application logs...$(NC)"
	@docker compose logs -f thoth-app

.PHONY: docker-ps
docker-ps: ## Show Docker service status
	@echo "$(YELLOW)Docker Service Status:$(NC)"
	@echo "====================="
	@docker compose ps

.PHONY: docker-status
docker-status: ## Show comprehensive Docker status for all environments
	@echo "$(YELLOW)Thoth Docker Status Overview:$(NC)"
	@echo "===================================="
	@echo "$(CYAN)Production Services:$(NC)"
	@-docker compose -f docker-compose.prod.yml ps 2>/dev/null || echo "  No production services running"
	@echo ""
	@echo "$(CYAN)Development Services:$(NC)"
	@-docker compose -f docker-compose.dev.yml ps 2>/dev/null || echo "  No development services running"
	@echo ""
	@echo "$(CYAN)Default Services:$(NC)"
	@-docker compose -f docker-compose.yml ps 2>/dev/null || echo "  No default services running"
	@echo ""
	@echo "$(CYAN)All Thoth-related Containers:$(NC)"
	@-docker ps --filter "name=thoth" --filter "name=letta" --filter "name=chroma" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  No Thoth containers running"

.PHONY: docker-volumes
docker-volumes: ## Show data storage overview
	@echo "$(YELLOW)Thoth Data Storage Overview:$(NC)"
	@echo "============================="
	@echo "$(CYAN)Local Filesystem (easily accessible):$(NC)"
	@-du -sh ./workspace 2>/dev/null || echo "  ./workspace/ - not created yet"
	@-du -sh ./data 2>/dev/null || echo "  ./data/ - not created yet"
	@-du -sh ./logs 2>/dev/null || echo "  ./logs/ - not created yet"
	@-du -sh ./cache 2>/dev/null || echo "  ./cache/ - not created yet"
	@echo ""
	@echo "$(CYAN)Docker-managed volumes (databases):$(NC)"
	@-docker volume ls --filter "name=thoth" --format "table {{.Name}}\t{{.Size}}" 2>/dev/null | head -1
	@-docker volume ls --filter "name=thoth" --format "table {{.Name}}\t{{.Size}}" 2>/dev/null | tail -n +2 | sort
	@echo ""
	@echo "$(GREEN)✓ Local files can be watched and backed up normally$(NC)"
	@echo "$(GREEN)✓ Database volumes preserve vector stores and memory$(NC)"

.PHONY: docker-health
docker-health: ## Check health of Docker services
	@echo "$(YELLOW)Checking Docker service health...$(NC)"
	@docker exec thoth-app python /app/docker/healthcheck.py --simple 2>/dev/null || echo "$(RED)Health check failed$(NC)"

.PHONY: docker-shell
docker-shell: ## Open shell in main application container
	@echo "$(YELLOW)Opening shell in Thoth application container...$(NC)"
	@docker exec -it thoth-app /bin/bash

.PHONY: docker-shell-dev
docker-shell-dev: ## Open shell in development container
	@echo "$(YELLOW)Opening shell in Thoth development container...$(NC)"
	@docker exec -it thoth-app-dev /bin/bash

.PHONY: docker-shutdown
docker-shutdown: ## Shutdown ALL Docker services and clean up (comprehensive)
	@echo "$(YELLOW)Shutting down ALL Thoth Docker services...$(NC)"
	@echo "$(CYAN)Stopping all docker-compose configurations...$(NC)"
	@-docker compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true
	@-docker compose -f docker-compose.dev.yml down --remove-orphans 2>/dev/null || true
	@-docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
	@echo "$(CYAN)Stopping any running Thoth containers...$(NC)"
	@-docker stop $$(docker ps -q --filter "name=thoth") 2>/dev/null || true
	@-docker stop $$(docker ps -q --filter "name=letta") 2>/dev/null || true
	@-docker stop $$(docker ps -q --filter "name=chromadb") 2>/dev/null || true
	@echo "$(CYAN)Cleaning up unused containers and networks...$(NC)"
	@-docker container prune -f 2>/dev/null || true
	@-docker network prune -f 2>/dev/null || true
	@echo "$(GREEN)✓ All Thoth Docker services shutdown complete$(NC)"

.PHONY: docker-shutdown-dev
docker-shutdown-dev: ## Shutdown only development services
	@echo "$(YELLOW)Shutting down development services...$(NC)"
	@-docker compose -f docker-compose.dev.yml down --remove-orphans 2>/dev/null || true
	@echo "$(GREEN)✓ Development services shutdown complete$(NC)"

.PHONY: docker-shutdown-prod
docker-shutdown-prod: ## Shutdown only production services
	@echo "$(YELLOW)Shutting down production services...$(NC)"
	@-docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
	@echo "$(GREEN)✓ Production services shutdown complete$(NC)"

.PHONY: docker-shutdown-service
docker-shutdown-service: ## Shutdown specific service (usage: make docker-shutdown-service SERVICE=chromadb)
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Error: Please specify SERVICE=<service_name>$(NC)"; \
		echo "$(YELLOW)Example: make docker-shutdown-service SERVICE=chromadb$(NC)"; \
		echo "$(YELLOW)Available services: thoth-api, thoth-mcp, chromadb, letta, letta-postgres$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Shutting down service: $(SERVICE)$(NC)"
	@-docker compose stop $(SERVICE) 2>/dev/null || true
	@-docker compose -f docker-compose.dev.yml stop $(SERVICE) 2>/dev/null || true
	@-docker compose -f docker-compose.prod.yml stop $(SERVICE) 2>/dev/null || true
	@echo "$(GREEN)✓ Service $(SERVICE) shutdown complete$(NC)"

.PHONY: docker-clean-cache
docker-clean-cache: ## Clean only Docker build cache (preserves images and data)
	@echo "$(YELLOW)Cleaning Docker build cache...$(NC)"
	@docker builder prune -f
	@echo "$(CYAN)Removing unused containers...$(NC)"
	@-docker container prune -f 2>/dev/null || true
	@echo "$(CYAN)Removing unused networks...$(NC)"
	@-docker network prune -f 2>/dev/null || true
	@echo "$(GREEN)✓ Docker cache cleanup complete$(NC)"

.PHONY: docker-clean
docker-clean: ## Clean Docker containers and unused images (preserves data)
	@echo "$(YELLOW)Cleaning Docker containers and unused images...$(NC)"
	@echo "$(CYAN)Stopping services...$(NC)"
	@-docker compose down --remove-orphans 2>/dev/null || true
	@echo "$(CYAN)Removing unused containers...$(NC)"
	@-docker container prune -f 2>/dev/null || true
	@echo "$(CYAN)Removing unused images...$(NC)"
	@-docker image prune -f 2>/dev/null || true
	@echo "$(CYAN)Removing unused networks...$(NC)"
	@-docker network prune -f 2>/dev/null || true
	@echo "$(GREEN)✓ Docker cleanup complete (data preserved)$(NC)"

.PHONY: docker-clean-all
docker-clean-all: ## Complete Docker cleanup including data (WARNING: deletes all data)
	@echo "$(RED)WARNING: This will shutdown and DELETE ALL Thoth Docker data!$(NC)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@echo "$(YELLOW)Performing complete shutdown and cleanup...$(NC)"
	@$(MAKE) docker-shutdown
	@echo "$(CYAN)Removing all volumes...$(NC)"
	@-docker compose -f docker-compose.yml down -v 2>/dev/null || true
	@-docker compose -f docker-compose.dev.yml down -v 2>/dev/null || true
	@-docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true
	@-docker volume prune -f 2>/dev/null || true
	@echo "$(CYAN)Removing Thoth images...$(NC)"
	@-docker rmi $$(docker images --filter "reference=*thoth*" -q) 2>/dev/null || true
	@-docker rmi $$(docker images --filter "reference=*letta*" -q) 2>/dev/null || true
	@echo "$(GREEN)✓ Complete Docker cleanup finished$(NC)"

.PHONY: docker-clean-volumes
docker-clean-volumes: ## Clean Docker volumes (WARNING: deletes all data)
	@echo "$(RED)WARNING: This will delete ALL Thoth data in Docker volumes!$(NC)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@echo "$(YELLOW)Removing Docker volumes...$(NC)"
	@docker compose down -v
	@docker volume prune -f
	@echo "$(GREEN)✓ Docker volumes cleaned$(NC)"

.PHONY: docker-restart
docker-restart: ## Restart Docker services
	@echo "$(YELLOW)Restarting Docker services...$(NC)"
	@docker compose restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

.PHONY: docker-rebuild
docker-rebuild: ## Rebuild and restart Docker services
	@echo "$(YELLOW)Rebuilding and restarting Docker services...$(NC)"
	@docker compose down
	@docker compose build --no-cache
	@docker compose up -d
	@echo "$(GREEN)✓ Services rebuilt and started$(NC)"

.PHONY: docker-init
docker-init: ## Initialize Docker environment (first-time setup)
	@echo "$(YELLOW)Initializing Docker environment...$(NC)"
	@if [ ! -f .env.docker ]; then \
		echo "$(YELLOW)Creating .env.docker from template...$(NC)"; \
		cp .env.docker.example .env.docker; \
		echo "$(GREEN)✓ Created .env.docker$(NC)"; \
		echo "$(YELLOW)Please edit .env.docker with your API keys$(NC)"; \
	else \
		echo "$(GREEN)✓ .env.docker already exists$(NC)"; \
	fi
	@echo "$(YELLOW)Initializing local workspace directories...$(NC)"
	@./init-workspace.sh
	@make docker-build
	@echo "$(GREEN)✓ Docker environment initialized$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Edit .env.docker with your API keys"
	@echo "  2. Run 'make docker-up' to start services"

# -----------------------------------------------------------------------------
# Combined Development Targets
# -----------------------------------------------------------------------------

.PHONY: docker-dev
docker-dev: ## Complete development setup with Docker
	@echo "$(YELLOW)Starting complete Docker development environment...$(NC)"
	@make docker-build-dev
	@make docker-up-dev
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "$(YELLOW)Services available at:$(NC)"
	@echo "  - API Server: http://localhost:8000"
	@echo "  - MCP Server: http://localhost:8001"
	@echo "  - ChromaDB: http://localhost:8003"
	@echo "  - Letta Server: http://localhost:8283"

.PHONY: docker-prod
docker-prod: ## Complete production setup with Docker
	@echo "$(YELLOW)Starting complete Docker production environment...$(NC)"
	@make docker-build-prod
	@make docker-up-prod
	@echo "$(GREEN)✓ Production environment ready$(NC)"

# Set default target
.DEFAULT_GOAL := help
