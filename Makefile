# =============================================================================
# Thoth Research Assistant - Streamlined Makefile
# =============================================================================
#
# Quick Start:
#   1. Set vault path: export OBSIDIAN_VAULT_PATH=/path/to/vault
#      OR set in .env.vault: OBSIDIAN_VAULT_PATH=/path/to/vault
#   2. Development mode: make dev
#   3. Production mode: make prod
#   4. Check health: make health
#   5. View logs: make dev-logs (dev) or make prod-logs (prod)
#
# Configuration Files:
#   - docker-compose.dev.yml  → Development (hot-reload enabled)
#   - docker-compose.yml      → Production (optimized, no hot-reload)
#
# =============================================================================

# Configuration Variables
# Set OBSIDIAN_VAULT_PATH in your .env.vault file or export as environment variable
OBSIDIAN_VAULT ?= $(OBSIDIAN_VAULT_PATH)
OBSIDIAN_VAULT_PATH ?= $(error OBSIDIAN_VAULT_PATH not set. Please set it in .env.vault or export it)
PLUGIN_SRC_DIR = obsidian-plugin/thoth-obsidian
PLUGIN_DEST_DIR = $(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian
WATCH_DIR ?= $(OBSIDIAN_VAULT_PATH)/thoth/papers/pdfs

# Colors
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
CYAN = \033[0;36m
NC = \033[0m

# =============================================================================
# MAIN COMMANDS
# =============================================================================

.PHONY: help
help: ## Show available commands
	@echo "$(GREEN)Thoth Research Assistant - Available Commands$(NC)"
	@echo "=============================================="
	@echo ""
	@echo "$(YELLOW)🚀 Quick Start:$(NC)"
	@echo "  $(GREEN)dev$(NC)                  Start development environment (microservices)"
	@echo "  $(GREEN)prod$(NC)                 Start production server (microservices)"
	@echo "  $(GREEN)health$(NC)               Check health of all services"
	@echo "  $(GREEN)deploy-and-start$(NC)     Deploy plugin + start ecosystem"
	@echo ""
	@echo "$(YELLOW)🔧 Development Mode:$(NC)"
	@echo "  $(GREEN)dev$(NC)                  Start dev environment (5 containers)"
	@echo "  $(GREEN)microservices$(NC)        Alias for 'make dev'"
	@echo "  $(GREEN)dev-status$(NC)           Check dev environment status"
	@echo "  $(GREEN)dev-logs$(NC)             View development logs (follow)"
	@echo "  $(GREEN)dev-stop$(NC)             Stop development environment"
	@echo "  $(GREEN)test-config$(NC)          Test configuration loading"
	@echo ""
	@echo "$(YELLOW)🚀 Production Mode:$(NC)"
	@echo "  $(GREEN)prod$(NC)                 Start production server (5 containers)"
	@echo "  $(GREEN)prod-microservices$(NC)   Alias for 'make prod'"
	@echo "  $(GREEN)prod-status$(NC)          Check production server status"
	@echo "  $(GREEN)prod-logs$(NC)            View production logs (follow)"
	@echo "  $(GREEN)prod-stop$(NC)            Stop production server"
	@echo "  $(GREEN)prod-restart$(NC)         Restart production server"
	@echo ""
	@echo "$(YELLOW)🔍 Service Management:$(NC)"
	@echo "  $(GREEN)start$(NC)                Start complete ecosystem (legacy)"
	@echo "  $(GREEN)stop$(NC)                 Stop all services"
	@echo "  $(GREEN)status$(NC)               Show service status"
	@echo "  $(GREEN)health$(NC)               Health check all services"
	@echo "  $(GREEN)logs$(NC)                 View service logs"
	@echo ""
	@echo "$(YELLOW)🔥 Hot-Reload:$(NC)"
	@echo "  $(GREEN)reload-settings$(NC)     Manually trigger settings reload"
	@echo "  $(GREEN)watch-settings$(NC)      Watch settings file changes live"
	@echo "  $(GREEN)test-hot-reload$(NC)     Test hot-reload end-to-end"
	@echo "  $(GREEN)hot-reload-status$(NC)   Check hot-reload status"
	@echo "  $(GREEN)enable-hot-reload-prod$(NC)  Enable hot-reload in production (use with caution)"
	@echo ""
	@echo "$(YELLOW)💻 Local Mode (No Docker):$(NC)"
	@echo "  $(GREEN)local-start$(NC)          Start services locally"
	@echo "  $(GREEN)local-stop$(NC)           Stop local services"
	@echo "  $(GREEN)dev-thoth-start$(NC)      Start all Thoth dev containers (not Letta)"
	@echo "  $(GREEN)dev-thoth-stop$(NC)       Stop all Thoth dev containers (not Letta)"
	@echo "  $(GREEN)dev-thoth-restart$(NC)    Restart all Thoth dev containers (not Letta)"
	@echo ""
	@echo "$(YELLOW)🔌 Plugin Development:$(NC)"
	@echo "  $(GREEN)deploy-plugin$(NC)        Deploy plugin with vault integration"
	@echo "  $(GREEN)verify-plugin$(NC)        Verify plugin deployment"
	@echo "  $(GREEN)plugin-dev$(NC)           Plugin watch mode (auto-rebuild)"
	@echo ""
	@echo "$(YELLOW)📚 Knowledge Base:$(NC)"
	@echo "  $(GREEN)rebuild-kb$(NC)           Rebuild entire knowledge base"
	@echo "  $(GREEN)agent$(NC)                Start interactive research agent"
	@echo "  $(GREEN)watch$(NC)                Start PDF directory watcher"
	@echo ""
	@echo "$(YELLOW)Release:$(NC)"
	@echo "  $(GREEN)release$(NC)              Generate changelog and release commands"
	@echo "  $(GREEN)release VERSION=x.y.z$(NC) Release with explicit version"
	@echo ""
	@echo "$(YELLOW)Diagnostics:$(NC)"
	@echo "  $(GREEN)check-vault$(NC)          Check vault integration status"
	@echo "  $(GREEN)check-deps$(NC)           Check required dependencies"
	@echo ""
	@echo "$(YELLOW)Configuration:$(NC)"
	@echo "  OBSIDIAN_VAULT_PATH=$(OBSIDIAN_VAULT_PATH)"
	@echo "  WATCH_DIR=$(WATCH_DIR)"
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo '  export OBSIDIAN_VAULT_PATH="/path/to/vault"'
	@echo '  make dev'
	@echo '  make health'
	@echo '  make prod'

# =============================================================================
# QUICK START COMMANDS
# =============================================================================

.PHONY: deploy-and-start
deploy-and-start: ## 🚀 ONE COMMAND: Deploy plugin + start complete ecosystem
	@echo "$(GREEN)🚀 THOTH COMPLETE SETUP$(NC)"
	@echo "========================="
	@make deploy-plugin OBSIDIAN_VAULT="$(OBSIDIAN_VAULT)"
	@echo ""
	@echo "$(YELLOW)Starting complete Thoth ecosystem...$(NC)"
	@make start OBSIDIAN_VAULT="$(OBSIDIAN_VAULT)"
	@echo ""
	@echo "$(GREEN)✅ COMPLETE SETUP FINISHED!$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "1. Configure API keys: $(OBSIDIAN_VAULT)/thoth/_thoth/settings.json"
	@echo "2. Check MCP plugins: $(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian/mcp-plugins.json"
	@echo "3. Reload Obsidian: Ctrl/Cmd+P → 'Reload app without saving'"
	@echo "4. Enable plugin: Settings → Community plugins → Enable 'Thoth'"
	@echo "5. Start researching! 🧠"

.PHONY: deploy-plugin
deploy-plugin: _check-vault _build-plugin ## Deploy Obsidian plugin with complete vault integration
	@echo "$(YELLOW)Deploying plugin with vault integration...$(NC)"
	@mkdir -p "$(PLUGIN_DEST_DIR)"
	@echo "$(CYAN)  Copying main.js...$(NC)"
	@cp $(PLUGIN_SRC_DIR)/dist/main.js "$(PLUGIN_DEST_DIR)/main.js"
	@echo "$(CYAN)  Copying manifest.json...$(NC)"
	@cp $(PLUGIN_SRC_DIR)/manifest.json "$(PLUGIN_DEST_DIR)/manifest.json"
	@echo "$(CYAN)  Copying styles.css...$(NC)"
	@cp $(PLUGIN_SRC_DIR)/styles.css "$(PLUGIN_DEST_DIR)/styles.css"
	@echo "$(CYAN)  Clearing Obsidian cache...$(NC)"
	@rm -rf ~/.config/obsidian/Cache/* 2>/dev/null || true
	@rm -rf ~/.config/obsidian/Code\ Cache/* 2>/dev/null || true
	@rm -rf ~/.config/obsidian/GPUCache/* 2>/dev/null || true
	@make _setup-vault-integration OBSIDIAN_VAULT="$(OBSIDIAN_VAULT)"
	@echo ""
	@echo "$(GREEN)✅ Plugin deployment complete!$(NC)"
	@echo ""
	@echo "$(YELLOW)📱 Next steps:$(NC)"
	@echo "  1. Close Obsidian completely (don't just reload)"
	@echo "  2. Reopen Obsidian"
	@echo "  3. Enable plugin: Settings → Community plugins → Enable 'Thoth'"
	@echo ""
	@echo "$(CYAN)Plugin files deployed:$(NC)"
	@ls -lh "$(PLUGIN_DEST_DIR)/" | grep -E "main.js|manifest.json|styles.css" || true

# =============================================================================
# SERVICE MANAGEMENT
# =============================================================================

# =============================================================================
# DEVELOPMENT ENVIRONMENT (docker-compose.dev.yml)
# =============================================================================

.PHONY: dev
dev: ## Start development environment with hot-reload (microservices mode)
	@echo "$(YELLOW)Starting Thoth development environment (microservices mode)...$(NC)"
	@echo "$(CYAN)Using separate containers for each service (5 containers)$(NC)"
	@echo ""
	@# Check if Letta is running, start if needed
	@bash scripts/check-letta.sh || exit 1
	@echo ""
	@if [ -z "$(OBSIDIAN_VAULT_PATH)" ]; then \
		if [ -f .env.vault ]; then \
			echo "$(CYAN)Loading vault path from .env.vault...$(NC)"; \
			export $$(cat .env.vault | grep -v '^#' | xargs); \
		fi; \
	fi; \
	if [ -z "$(OBSIDIAN_VAULT_PATH)" ] && [ -z "$$OBSIDIAN_VAULT_PATH" ]; then \
		echo "$(RED)ERROR: OBSIDIAN_VAULT_PATH not set$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Set it in one of these ways:$(NC)"; \
		echo "  1. Export: export OBSIDIAN_VAULT_PATH=/path/to/vault"; \
		echo "  2. .env.vault: echo 'OBSIDIAN_VAULT_PATH=/path/to/vault' > .env.vault"; \
		echo "  3. Command: make dev OBSIDIAN_VAULT_PATH=/path/to/vault"; \
		exit 1; \
	fi; \
	VAULT_PATH="$${OBSIDIAN_VAULT_PATH:-$(OBSIDIAN_VAULT_PATH)}"; \
	echo "$(CYAN)Using vault: $$VAULT_PATH$(NC)"; \
	OBSIDIAN_VAULT_PATH="$$VAULT_PATH" docker compose -f docker-compose.dev.yml --profile microservices up -d
	@echo ""
	@echo "$(GREEN)✅ Development environment started$(NC)"
	@echo ""
	@make dev-status

.PHONY: microservices
microservices: ## Alias for 'make dev' (microservices is now the default)
	@make dev

.PHONY: dev-status
dev-status: ## Check development environment status
	@echo "$(YELLOW)Development Services Status:$(NC)"
	@echo "============================"
	@docker compose -f docker-compose.dev.yml ps
	@echo ""
	@make health

.PHONY: dev-logs
dev-logs: ## View development logs (follow)
	@echo "$(YELLOW)Development Logs (Ctrl+C to exit)$(NC)"
	@echo "=================================="
	@docker compose -f docker-compose.dev.yml logs -f

.PHONY: dev-stop
dev-stop: ## Stop development environment (both modes)
	@echo "$(YELLOW)Stopping development environment...$(NC)"
	@docker compose -f docker-compose.dev.yml --profile microservices down
	@echo "$(GREEN)✅ Development environment stopped$(NC)"

# =============================================================================
# HEALTH & DIAGNOSTICS
# =============================================================================

.PHONY: health
health: ## Check health of all services
	@echo "$(YELLOW)Service Health Checks:$(NC)"
	@echo "====================="
	@echo -n "  API (8000):         "
	@curl -so /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null | grep -qE '^(200|503)' && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo -n "  MCP (8082):         "
	@curl -sf http://localhost:8082/health >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo -n "  Discovery:          "
	@docker ps --filter name=thoth-dev-discovery --format '{{.Status}}' 2>/dev/null | grep -q 'healthy' && echo "$(GREEN)✓ Healthy$(NC)" || (docker ps --filter name=thoth-dev-discovery --format '{{.Status}}' 2>/dev/null | grep -q 'Up' && echo "$(YELLOW)⚡ Running$(NC)" || echo "$(RED)✗ Down$(NC)")
	@echo -n "  Monitor:            "
	@docker ps --filter name=thoth-dev-pdf-monitor --format '{{.Status}}' 2>/dev/null | grep -q 'Up' && echo "$(GREEN)✓ Running$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo -n "  Dashboard:          "
	@docker ps --filter name=thoth-dev-dashboard --format '{{.Status}}' 2>/dev/null | grep -q 'Up' && echo "$(GREEN)✓ Running$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo -n "  Letta (8283):       "
	@curl -sf http://localhost:8283/v1/health >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Down$(NC)"

.PHONY: test-config
test-config: ## Test configuration loading
	@echo "$(YELLOW)Testing configuration...$(NC)"
	@docker compose -f docker-compose.dev.yml run --rm thoth-api python -c "\
		from thoth.config import config; \
		print('$(GREEN)✓ Config loaded successfully$(NC)'); \
		print(f'  Vault root: {config.vault_root}'); \
		print(f'  Settings file: {config.vault_root}/thoth/_thoth/settings.json'); \
		print(f'  Workspace: {config.vault_root}/thoth/_thoth')" 2>/dev/null || \
		echo "$(RED)✗ Configuration test failed$(NC)"

# =============================================================================
# HOT-RELOAD COMMANDS
# =============================================================================

.PHONY: reload-settings
reload-settings: ## Manually trigger settings reload (tests hot-reload)
	@echo "$(YELLOW)Testing hot-reload by touching settings file...$(NC)"
	@if [ -z "$(OBSIDIAN_VAULT_PATH)" ]; then \
		echo "$(RED)ERROR: OBSIDIAN_VAULT_PATH not set$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(OBSIDIAN_VAULT_PATH)/thoth/_thoth/settings.json" ]; then \
		echo "$(RED)ERROR: Settings file not found$(NC)"; \
		exit 1; \
	fi
	@touch "$(OBSIDIAN_VAULT_PATH)/thoth/_thoth/settings.json"
	@echo "$(GREEN)✓ Settings file touched, watching logs for reload...$(NC)"
	@echo ""
	@echo "$(YELLOW)Check logs with: make dev-logs$(NC)"
	@sleep 3
	@docker compose -f docker-compose.dev.yml logs --tail=20 thoth-api | grep -i "reload" || echo "$(YELLOW)No reload messages yet, may take a few seconds$(NC)"

.PHONY: watch-settings
watch-settings: ## Watch settings file for changes (live monitoring)
	@echo "$(YELLOW)Watching settings file for changes...$(NC)"
	@echo "$(CYAN)Edit $(OBSIDIAN_VAULT_PATH)/thoth/_thoth/settings.json in another window$(NC)"
	@echo "$(CYAN)Logs will appear below (Ctrl+C to stop)$(NC)"
	@echo ""
	@docker compose -f docker-compose.dev.yml logs -f thoth-api | grep --line-buffered -i "reload\|settings"

.PHONY: test-hot-reload
test-hot-reload: ## Test hot-reload functionality end-to-end
	@echo "$(GREEN)🧪 Testing Hot-Reload Functionality$(NC)"
	@echo "====================================="
	@echo ""
	@echo "$(YELLOW)Step 1: Check hot-reload is enabled$(NC)"
	@curl -sf http://localhost:8000/health/hot-reload | jq . || (echo "$(RED)✗ API not responding$(NC)" && exit 1)
	@echo "$(GREEN)✓ Hot-reload endpoint responding$(NC)"
	@echo ""
	@echo "$(YELLOW)Step 2: Trigger settings reload$(NC)"
	@touch "$(OBSIDIAN_VAULT_PATH)/thoth/_thoth/settings.json"
	@echo "$(GREEN)✓ Settings file touched$(NC)"
	@echo ""
	@echo "$(YELLOW)Step 3: Wait for reload (3 seconds)$(NC)"
	@sleep 3
	@echo ""
	@echo "$(YELLOW)Step 4: Check logs for reload message$(NC)"
	@docker compose -f docker-compose.dev.yml logs --tail=10 thoth-api | grep -i "reload" && echo "$(GREEN)✓ Settings reloaded successfully!$(NC)" || echo "$(RED)✗ No reload detected$(NC)"
	@echo ""
	@echo "$(GREEN)✅ Hot-reload test complete!$(NC)"

.PHONY: hot-reload-status
hot-reload-status: ## Check hot-reload status for all services
	@echo "$(YELLOW)Hot-Reload Status$(NC)"
	@echo "================="
	@echo ""
	@echo "$(CYAN)API Server:$(NC)"
	@curl -sf http://localhost:8000/health/hot-reload 2>/dev/null | jq . || echo "$(RED)Not available$(NC)"
	@echo ""
	@echo "$(CYAN)Settings File:$(NC)"
	@ls -lh "$(OBSIDIAN_VAULT_PATH)/thoth/_thoth/settings.json" 2>/dev/null || echo "$(RED)Not found$(NC)"
	@echo ""
	@echo "$(CYAN)Environment Variables:$(NC)"
	@docker compose -f docker-compose.dev.yml exec -T thoth-api env | grep -E "HOT_RELOAD|DOCKER_ENV" || echo "$(RED)Not set$(NC)"

.PHONY: enable-hot-reload-prod
enable-hot-reload-prod: ## Enable hot-reload in production (use with caution)
	@echo "$(YELLOW)⚠️  Enabling hot-reload in production...$(NC)"
	@echo "$(RED)WARNING: This is for testing/development only!$(NC)"
	@echo ""
	@bash -c ' \
		if [ -f .env.production ]; then \
			if grep -q "^THOTH_HOT_RELOAD=" .env.production; then \
				sed -i "s/^THOTH_HOT_RELOAD=.*/THOTH_HOT_RELOAD=1/" .env.production; \
			else \
				echo "THOTH_HOT_RELOAD=1" >> .env.production; \
			fi; \
		else \
			echo "THOTH_HOT_RELOAD=1" > .env.production; \
		fi; \
		echo "$(GREEN)✓ Hot-reload enabled in .env.production$(NC)"; \
		echo ""; \
		echo "$(YELLOW)Restart production for changes to take effect:$(NC)"; \
		echo "  make prod-restart"; \
	'

# =============================================================================
# LEGACY START COMMAND (redirects to dev)
# =============================================================================

.PHONY: start
start: ## Start complete Thoth ecosystem (uses docker-compose.dev.yml)
	@echo "$(YELLOW)Note: 'make start' uses development mode$(NC)"
	@echo "$(CYAN)For production, use: make prod$(NC)"
	@echo ""

# =============================================================================
# LETTA & THOTH INDEPENDENT SERVICE MANAGEMENT
# =============================================================================
# Letta is now independent and can be used by multiple projects.
# Start Letta first, then start Thoth.

.PHONY: letta-start
letta-start: ## Start INDEPENDENT Letta services (generic, multi-project)
	@echo "$(YELLOW)Starting INDEPENDENT Letta services...$(NC)"
	@echo "$(CYAN)Letta can be used by multiple projects$(NC)"
	@bash scripts/letta-start.sh

.PHONY: letta-stop
letta-stop: ## Stop Letta services (WARNING: affects ALL projects)
	@echo "$(YELLOW)Stopping Letta services...$(NC)"
	@echo "$(RED)⚠️  WARNING: This will affect ALL projects using Letta!$(NC)"
	@bash scripts/letta-stop.sh

.PHONY: letta-status
letta-status: ## Check Letta services status
	@bash scripts/letta-status.sh

.PHONY: letta-restart
letta-restart: ## Restart Letta services (WARNING: affects ALL projects)
	@bash scripts/letta-restart.sh

.PHONY: letta-logs
letta-logs: ## View Letta server logs
	@docker logs -f letta-server

.PHONY: thoth-start
thoth-start: ## Start Thoth services (requires Letta to be running)
	@echo "$(YELLOW)Starting Thoth services...$(NC)"
	@bash scripts/thoth-start.sh

.PHONY: thoth-stop
thoth-stop: ## Stop Thoth services (does NOT stop Letta)
	@echo "$(YELLOW)Stopping Thoth services...$(NC)"
	@bash scripts/thoth-stop.sh

.PHONY: thoth-status
thoth-status: ## Check Thoth services status
	@bash scripts/thoth-status.sh

.PHONY: thoth-restart
thoth-restart: ## Restart Thoth services (does NOT restart Letta)
	@bash scripts/thoth-restart.sh

.PHONY: thoth-logs
thoth-logs: ## View Thoth logs
	@docker logs -f thoth-api

	@make dev

.PHONY: local-start
local-start: ## Start services locally (Letta in Docker, rest local)
	@echo "$(YELLOW)Starting Thoth services (hybrid mode)...$(NC)"
	@mkdir -p ./workspace/data/chromadb ./workspace/exports ./workspace/logs ./workspace/data/letta
	@echo "$(CYAN)Starting Letta + PostgreSQL (Docker)...$(NC)"
	@docker compose -f docker-compose.dev.yml up -d letta-postgres letta
	@sleep 3
	@echo "$(CYAN)Starting API server...$(NC)"
	@bash -c 'source .env.vault 2>/dev/null || true; VAULT="$${OBSIDIAN_VAULT_PATH}"; \
	PYTHONPATH=src THOTH_WORKSPACE_DIR="$$VAULT/thoth/_thoth" THOTH_SETTINGS_FILE="$$VAULT/thoth/_thoth/settings.json" DOCKER_ENV=false THOTH_LETTA_URL=http://localhost:8283 LOG_LEVEL=WARNING uv run python -m thoth api --host 0.0.0.0 --port 8000 > ./workspace/logs/api.log 2>&1 &'
	@sleep 3
	@echo "$(CYAN)Starting MCP server...$(NC)"
	@bash -c 'source .env.vault 2>/dev/null || true; VAULT="$${OBSIDIAN_VAULT_PATH}"; \
	PYTHONPATH=src THOTH_WORKSPACE_DIR="$$VAULT/thoth/_thoth" THOTH_SETTINGS_FILE="$$VAULT/thoth/_thoth/settings.json" DOCKER_ENV=false LOG_LEVEL=WARNING uv run python -m thoth mcp http --host 0.0.0.0 --port 8001 > ./workspace/logs/mcp.log 2>&1 &'
	@sleep 2
	@echo "$(CYAN)Starting Discovery service...$(NC)"
	@bash -c 'source .env.vault 2>/dev/null || true; VAULT="$${OBSIDIAN_VAULT_PATH}"; \
	PYTHONPATH=src THOTH_WORKSPACE_DIR="$$VAULT/thoth/_thoth" THOTH_SETTINGS_FILE="$$VAULT/thoth/_thoth/settings.json" DOCKER_ENV=false LOG_LEVEL=WARNING uv run python -m thoth discovery server > ./workspace/logs/discovery.log 2>&1 &'
	@sleep 2
	@bash -c 'source .env.vault 2>/dev/null || true; VAULT="$${OBSIDIAN_VAULT_PATH}"; \
	WATCH="$(WATCH_DIR)"; \
	echo "$(CYAN)Starting PDF Monitor (watching $$WATCH)...$(NC)"; \
	PYTHONPATH=src THOTH_WORKSPACE_DIR="$$VAULT/thoth/_thoth" THOTH_SETTINGS_FILE="$$VAULT/thoth/_thoth/settings.json" DOCKER_ENV=false LOG_LEVEL=INFO uv run python -m thoth monitor --watch-dir "$$WATCH" --optimized --recursive > ./workspace/logs/monitor.log 2>&1 &'
	@sleep 1
	@echo "$(GREEN)✅ All services started:$(NC)"
	@echo "  • Letta Memory: http://localhost:8283 $(CYAN)(Docker)$(NC)"
	@echo "  • API Server: http://localhost:8000 $(CYAN)(Local)$(NC)"
	@echo "  • MCP Server: http://localhost:8001 $(CYAN)(Local)$(NC)"
	@echo "  • Discovery: http://localhost:8004 $(CYAN)(Local)$(NC)"
	@echo "  • PDF Monitor: Watching $(WATCH_DIR) $(CYAN)(Local)$(NC)"
	@echo ""
	@echo "$(YELLOW)Logs: ./workspace/logs/ (in project repo)$(NC)"
	@echo "$(YELLOW)To stop: make local-stop$(NC)"

.PHONY: stop
stop: ## Stop all Thoth services (both dev and prod)
	@echo "$(YELLOW)Stopping all Thoth services...$(NC)"
	@echo "$(CYAN)Stopping development services...$(NC)"
	@docker compose -f docker-compose.dev.yml down 2>/dev/null || true
	@echo "$(CYAN)Stopping production services...$(NC)"
	@docker compose -f docker-compose.yml down 2>/dev/null || true
	@echo "$(GREEN)✅ All services stopped$(NC)"

# =============================================================================
# PRODUCTION DEPLOYMENT (docker-compose.yml)
# =============================================================================

.PHONY: prod
prod: ## Start production server (microservices mode)
	@echo "$(GREEN)🚀 Starting Thoth Production Server$(NC)"
	@echo "=========================================================="
	@echo "$(CYAN)Using separate containers for each service (5 containers)$(NC)"
	@echo ""
	@bash -c ' \
		if [ -z "$(OBSIDIAN_VAULT_PATH)" ]; then \
			if [ -f .env.vault ]; then \
				echo "$(CYAN)Loading vault path from .env.vault...$(NC)"; \
				source .env.vault; \
			fi; \
		fi; \
		if [ -f .env.production ]; then \
			echo "$(CYAN)Loading production config from .env.production...$(NC)"; \
			source .env.production; \
		fi; \
		VAULT_PATH="$${OBSIDIAN_VAULT_PATH:-$(OBSIDIAN_VAULT_PATH)}"; \
		if [ -z "$$VAULT_PATH" ] && [ -z "$$THOTH_DATA_MOUNT" ]; then \
			echo "$(RED)ERROR: OBSIDIAN_VAULT_PATH not set$(NC)"; \
			echo ""; \
			echo "$(YELLOW)Set it in one of these ways:$(NC)"; \
			echo "  1. Export: export OBSIDIAN_VAULT_PATH=/path/to/vault"; \
			echo "  2. .env.vault: echo \"OBSIDIAN_VAULT_PATH=/path/to/vault\" > .env.vault"; \
			echo "  3. Command: make prod OBSIDIAN_VAULT_PATH=/path/to/vault"; \
			echo ""; \
			echo "$(YELLOW)For your setup:$(NC)"; \
			echo "  OBSIDIAN_VAULT_PATH=\"/path/to/your/vault\""; \
			exit 1; \
		fi; \
		if [ -z "$$THOTH_DATA_MOUNT" ] && [ -n "$$VAULT_PATH" ]; then \
			export THOTH_DATA_MOUNT="$$VAULT_PATH/thoth/_thoth"; \
		fi; \
		echo "$(CYAN)Vault: $$VAULT_PATH$(NC)"; \
		echo "$(CYAN)Data mount: $$THOTH_DATA_MOUNT$(NC)"; \
		if [ -f "$$THOTH_DATA_MOUNT/settings.json" ]; then \
			echo "$(GREEN)✓ Found settings.json$(NC)"; \
		else \
			echo "$(YELLOW)⚠️  No settings.json at $$THOTH_DATA_MOUNT/settings.json$(NC)"; \
			echo "$(YELLOW)   Configure API keys in vault/thoth/_thoth/settings.json$(NC)"; \
		fi; \
		echo ""; \
		echo "$(CYAN)Building and starting production containers...$(NC)"; \
		echo "$(CYAN)Using: docker-compose.yml (optimized, no hot-reload)$(NC)"; \
		export THOTH_DATA_MOUNT; \
		export OBSIDIAN_VAULT_PATH="$$VAULT_PATH"; \
		USER_ID=$$(id -u) GROUP_ID=$$(id -g) docker compose up -d --build; \
		echo ""; \
		echo "$(YELLOW)Waiting for services to initialize...$(NC)"; \
		sleep 15; \
		echo ""; \
		echo "$(GREEN)✅ Production Server Started!$(NC)"; \
		echo ""; \
		make prod-status; \
	'

.PHONY: prod-microservices
prod-microservices: ## Alias for 'make prod' (microservices is now the default)
	@make prod

.PHONY: prod-stop
prod-stop: ## Stop production server
	@echo "$(YELLOW)Stopping production services...$(NC)"
	@docker compose stop
	@echo "$(GREEN)✅ Production services stopped$(NC)"

.PHONY: prod-restart
prod-restart: ## Restart production server
	@echo "$(YELLOW)Restarting production services...$(NC)"
	@make prod-stop
	@sleep 2
	@make prod

.PHONY: prod-logs
prod-logs: ## View production logs (follow)
	@echo "$(YELLOW)Production Logs (Ctrl+C to exit)$(NC)"
	@echo "================================"
	@docker compose -f docker-compose.yml logs -f

.PHONY: prod-status
prod-status: ## Check production server status
	@echo "$(YELLOW)Production Service Status:$(NC)"
	@echo "=========================="
	@docker compose -f docker-compose.yml ps
	@echo ""
	@echo "$(YELLOW)Health Checks:$(NC)"
	@echo -n "  API (8080):      "
	@curl -sf http://localhost:8080/health >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo -n "  MCP (8081):      "
	@curl -sf http://localhost:8081/health >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo -n "  Letta (8283):    "
	@curl -sf http://localhost:8283/v1/health >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Down$(NC)"
	@echo ""
	@echo "$(YELLOW)Access Points:$(NC)"
	@echo "  • API Server:    $(CYAN)http://localhost:8080$(NC)"
	@echo "  • MCP Server:    $(CYAN)http://localhost:8081$(NC)"
	@echo "  • Letta Memory:  $(CYAN)http://localhost:8283$(NC)"

.PHONY: prod-clean
prod-clean: ## Clean production deployment (WARNING: deletes volumes)
	@echo "$(RED)⚠️  WARNING: This will delete all database data!$(NC)"
	@echo "$(YELLOW)This includes Letta memory and ChromaDB vectors.$(NC)"
	@echo ""
	@read -p "Are you sure? (type 'yes' to confirm): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(YELLOW)Stopping and removing containers and volumes...$(NC)"; \
		docker-compose --env-file .env.production down -v; \
		echo "$(GREEN)✅ Production environment cleaned$(NC)"; \
	else \
		echo "$(CYAN)Cancelled.$(NC)"; \
	fi

# =============================================================================
# DEVELOPMENT (CONTINUED)
# =============================================================================

.PHONY: watch
watch: ## Start PDF directory watcher (hot-reloads from settings.json)
	@echo "$(YELLOW)Starting PDF directory watcher with hot reload...$(NC)"
	@echo "$(CYAN)Watching: $(WATCH_DIR)$(NC)"
	@echo "$(CYAN)Hot reload: Edit thoth/_thoth/settings.json → monitor auto-reloads!$(NC)"
	@echo ""
	@PYTHONPATH=src THOTH_WORKSPACE_DIR=./workspace DOCKER_ENV=false uv run python -m thoth monitor --watch-dir "$(WATCH_DIR)" --optimized --recursive > ./workspace/logs/monitor.log 2>&1 &
	@echo "$(GREEN)✅ PDF watcher started with hot reload$(NC)"
	@echo "$(YELLOW)Logs: ./workspace/logs/monitor.log$(NC)"
	@echo "$(YELLOW)To stop: pkill -f 'thoth monitor'$(NC)"

.PHONY: dev-thoth-start
dev-thoth-start: ## Start all Thoth dev containers (does not start Letta)
	@echo "$(YELLOW)Starting Thoth dev containers...$(NC)"
	@docker compose -f docker-compose.dev.yml --profile microservices up -d
	@echo "$(GREEN)✅ Thoth dev containers started$(NC)"
	@make dev-status

.PHONY: dev-thoth-stop
dev-thoth-stop: ## Stop all Thoth dev containers (does not stop Letta)
	@echo "$(YELLOW)Stopping Thoth dev containers...$(NC)"
	@docker compose -f docker-compose.dev.yml --profile microservices stop
	@echo "$(GREEN)✅ Thoth dev containers stopped$(NC)"

.PHONY: dev-thoth-restart
dev-thoth-restart: ## Restart all Thoth dev containers (does not restart Letta)
	@echo "$(YELLOW)Restarting Thoth dev containers...$(NC)"
	@docker compose -f docker-compose.dev.yml --profile microservices stop
	@docker compose -f docker-compose.dev.yml --profile microservices up -d
	@echo "$(GREEN)✅ Thoth dev containers restarted$(NC)"
	@make dev-status

.PHONY: local-stop
local-stop: ## Stop local services and Letta Docker containers
	@echo "$(YELLOW)Stopping local Thoth services...$(NC)"
	-@pkill -f "python.*thoth api" 2>/dev/null || true
	-@pkill -f "python.*thoth mcp" 2>/dev/null || true
	-@pkill -f "python.*thoth discovery" 2>/dev/null || true
	-@pkill -f "python.*thoth monitor" 2>/dev/null || true
	@sleep 1
	@echo "$(CYAN)Stopping Letta Docker containers...$(NC)"
	-@docker compose -f docker-compose.dev.yml stop letta letta-postgres 2>/dev/null || true
	-@docker compose -f docker-compose.dev.yml rm -f letta letta-postgres 2>/dev/null || true
	@echo "$(GREEN)✅ All local services stopped$(NC)"

.PHONY: restart
restart: ## Restart all services
	@make stop
	@make start

.PHONY: status
status: ## Show status of all services
	@echo "$(YELLOW)Thoth Service Status$(NC)"
	@echo "==================="
	@if docker compose -f docker-compose.dev.yml ps --quiet | grep -q .; then \
		docker compose -f docker-compose.dev.yml ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"; \
	else \
		echo "$(RED)No services running$(NC)"; \
		echo "$(YELLOW)Run 'make start' to start services$(NC)"; \
	fi

# =============================================================================
# PLUGIN DEVELOPMENT
# =============================================================================

.PHONY: plugin-dev
plugin-dev: ## Plugin development mode (watch + auto-rebuild)
	@echo "$(YELLOW)Starting plugin development mode...$(NC)"
	@echo "$(YELLOW)Plugin will auto-rebuild on file changes$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm install
	@cd $(PLUGIN_SRC_DIR) && npm run watch

.PHONY: verify-plugin
verify-plugin: ## Verify plugin deployment and show file info
	@echo "$(YELLOW)Verifying Plugin Deployment$(NC)"
	@echo "=========================="
	@echo ""
	@echo "$(CYAN)📁 Plugin Directory:$(NC)"
	@ls -lh "$(PLUGIN_DEST_DIR)/" 2>/dev/null || (echo "$(RED)❌ Plugin not found$(NC)" && exit 1)
	@echo ""
	@echo "$(CYAN)✅ Required Files:$(NC)"
	@test -f "$(PLUGIN_DEST_DIR)/main.js" && echo "  ✓ main.js ($$(du -h '$(PLUGIN_DEST_DIR)/main.js' | cut -f1))" || echo "  $(RED)✗ main.js missing$(NC)"
	@test -f "$(PLUGIN_DEST_DIR)/manifest.json" && echo "  ✓ manifest.json ($$(du -h '$(PLUGIN_DEST_DIR)/manifest.json' | cut -f1))" || echo "  $(RED)✗ manifest.json missing$(NC)"
	@test -f "$(PLUGIN_DEST_DIR)/styles.css" && echo "  ✓ styles.css ($$(du -h '$(PLUGIN_DEST_DIR)/styles.css' | cut -f1))" || echo "  $(RED)✗ styles.css missing$(NC)"
	@echo ""
	@echo "$(CYAN)📱 Mobile Keyboard Fix:$(NC)"
	@if grep -q "keyboard-visible" "$(PLUGIN_DEST_DIR)/styles.css" 2>/dev/null; then \
		count=$$(grep -c "keyboard-visible" "$(PLUGIN_DEST_DIR)/styles.css"); \
		echo "  ✓ Mobile keyboard CSS found ($$count occurrences)"; \
	else \
		echo "  $(RED)✗ Mobile keyboard CSS missing$(NC)"; \
	fi
	@echo ""
	@echo "$(CYAN)🕐 Last Modified:$(NC)"
	@stat -c "  %y %n" "$(PLUGIN_DEST_DIR)/main.js" "$(PLUGIN_DEST_DIR)/manifest.json" "$(PLUGIN_DEST_DIR)/styles.css" 2>/dev/null | sed 's|$(PLUGIN_DEST_DIR)/|  |'
	@echo ""
	@if [ -f "$(PLUGIN_DEST_DIR)/main.js" ] && [ -f "$(PLUGIN_DEST_DIR)/manifest.json" ] && [ -f "$(PLUGIN_DEST_DIR)/styles.css" ]; then \
		echo "$(GREEN)✅ Plugin deployment verified!$(NC)"; \
	else \
		echo "$(RED)❌ Plugin deployment incomplete$(NC)"; \
		echo "$(YELLOW)Run: make deploy-plugin$(NC)"; \
	fi

.PHONY: logs
logs: ## View Thoth service logs
	@echo "$(YELLOW)Thoth Service Logs (Ctrl+C to exit)$(NC)"
	@echo "=========================="
	@docker compose -f docker-compose.dev.yml logs -f

.PHONY: clean
clean: ## Clean all build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm run clean 2>/dev/null || true
	@rm -rf $(PLUGIN_SRC_DIR)/dist
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

.PHONY: clean-logs
clean-logs: ## Clean old/large log files (truncates >10MB, deletes >7 days old)
	@echo "$(YELLOW)Cleaning log files...$(NC)"
	@find ./workspace/logs -name "*.log" -type f -size +10M -exec sh -c 'echo "Truncating: $$1" && : > "$$1"' _ {} \; 2>/dev/null || true
	@find ./workspace/logs -name "*.log.*" -mtime +7 -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Logs cleaned (>10MB truncated, >7 days deleted)$(NC)"

# =============================================================================
# KNOWLEDGE BASE MANAGEMENT
# =============================================================================

.PHONY: rebuild-kb
rebuild-kb: ## Rebuild entire knowledge base from vault data
	@echo "$(YELLOW)Rebuilding knowledge base from vault data...$(NC)"
	@uv run python -c "from thoth.services.service_manager import ServiceManager; from thoth.utilities.config import get_config; import asyncio; async def rebuild(): config = get_config(); sm = ServiceManager(config); await sm.rag.rebuild_index(); print('✅ Knowledge base rebuilt!'); asyncio.run(rebuild())"

.PHONY: agent
agent: ## Start interactive research agent
	@echo "$(YELLOW)Starting Thoth research agent...$(NC)"
	@uv run python -m thoth agent

# =============================================================================
# DIAGNOSTICS
# =============================================================================

.PHONY: check-vault
check-vault: ## Check Obsidian vault integration status
	@if [ ! -d "$(OBSIDIAN_VAULT)" ]; then \
		echo "$(RED)❌ Vault not found: $(OBSIDIAN_VAULT)$(NC)"; \
		echo "$(YELLOW)Set correct path: make deploy-plugin OBSIDIAN_VAULT=\"/your/vault/path\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Vault Integration Status$(NC)"
	@echo "========================"
	@echo "Vault: $(OBSIDIAN_VAULT)"
	@echo ""
	@echo -n "Plugin: "
	@if [ -d "$(PLUGIN_DEST_DIR)" ]; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌$(NC)"; fi
	@echo -n "Workspace: "
	@if [ -d "$(OBSIDIAN_VAULT)/.thoth" ]; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌$(NC)"; fi
	@echo -n "Settings: "
	@if [ -f "$(OBSIDIAN_VAULT)/.thoth.settings.json" ]; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌$(NC)"; fi
	@echo -n "MCP Config: "
	@if [ -f "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json" ]; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌$(NC)"; fi
	@echo -n "Prompts: "
	@if [ -d "$(OBSIDIAN_VAULT)/thoth/_thoth/prompts" ] && [ -n "$$(find '$(OBSIDIAN_VAULT)/thoth/_thoth/prompts' -name '*.j2' 2>/dev/null)" ]; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌$(NC)"; fi
	@echo ""
	@if [ -d "$(OBSIDIAN_VAULT)/thoth/_thoth/prompts" ]; then \
		echo "Prompt templates: $$(find '$(OBSIDIAN_VAULT)/thoth/_thoth/prompts' -name '*.j2' 2>/dev/null | wc -l)"; \
	fi
	@if [ -d "$(OBSIDIAN_VAULT)/.thoth/data/pdfs" ]; then \
		echo "PDF files: $$(find '$(OBSIDIAN_VAULT)/.thoth/data/pdfs' -name '*.pdf' 2>/dev/null | wc -l)"; \
	fi

.PHONY: check-deps
check-deps: ## Check required dependencies
	@echo "$(YELLOW)Dependency Status$(NC)"
	@echo "================="
	@echo -n "Docker: "
	@if command -v docker >/dev/null 2>&1; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌ Required$(NC)"; fi
	@echo -n "Node.js: "
	@if command -v node >/dev/null 2>&1; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌ Required$(NC)"; fi
	@echo -n "npm: "
	@if command -v npm >/dev/null 2>&1; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌ Required$(NC)"; fi
	@echo -n "Python: "
	@if command -v python3 >/dev/null 2>&1; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌ Required$(NC)"; fi
	@echo -n "uv: "
	@if command -v uv >/dev/null 2>&1; then echo "$(GREEN)✅$(NC)"; else echo "$(YELLOW)○ Optional$(NC)"; fi

# =============================================================================
# ADVANCED COMMANDS
# =============================================================================

.PHONY: reset-vault
reset-vault: ## Reset vault integration (WARNING: removes Thoth files)
	@echo "$(RED)This will reset Thoth integration in: $(OBSIDIAN_VAULT)$(NC)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@rm -rf "$(OBSIDIAN_VAULT)/.thoth" 2>/dev/null || true
	@rm -f "$(OBSIDIAN_VAULT)/.thoth.settings.json" 2>/dev/null || true
	@rm -rf "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian" 2>/dev/null || true
	@echo "$(GREEN)✅ Vault integration reset$(NC)"
	@echo "$(YELLOW)Run 'make deploy-plugin' to set up again$(NC)"

.PHONY: backup-vault-config
backup-vault-config: ## Backup vault Thoth configuration
	@echo "$(YELLOW)Backing up vault configuration...$(NC)"
	@mkdir -p backups
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	if [ -f "$(OBSIDIAN_VAULT)/.thoth.settings.json" ]; then \
		cp "$(OBSIDIAN_VAULT)/.thoth.settings.json" "backups/thoth.settings.$$timestamp.json"; \
		echo "$(GREEN)✅ Settings backed up$(NC)"; \
	fi; \
	if [ -f "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json" ]; then \
		cp "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json" "backups/mcp-plugins.$$timestamp.json"; \
		echo "$(GREEN)✅ MCP config backed up$(NC)"; \
	fi

# =============================================================================
# INTERNAL HELPERS (DO NOT CALL DIRECTLY)
# =============================================================================

.PHONY: _check-vault
_check-vault:
	@if [ ! -d "$(OBSIDIAN_VAULT)" ]; then \
		echo "$(RED)❌ Obsidian vault not found: $(OBSIDIAN_VAULT)$(NC)"; \
		echo "$(YELLOW)Set correct path: make deploy-plugin OBSIDIAN_VAULT=\"/your/vault/path\"$(NC)"; \
		exit 1; \
	fi

.PHONY: _build-plugin
_build-plugin:
	@echo "$(YELLOW)Building Obsidian plugin...$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm install
	@cd $(PLUGIN_SRC_DIR) && npm run build
	@echo "$(GREEN)✅ Plugin built$(NC)"

.PHONY: _setup-vault-integration
_setup-vault-integration:
	@echo "$(YELLOW)Setting up vault integration...$(NC)"
	@mkdir -p "$(OBSIDIAN_VAULT)/thoth/_thoth/prompts"
	@mkdir -p "$(OBSIDIAN_VAULT)/thoth/_thoth/skills"
	@mkdir -p "$(OBSIDIAN_VAULT)/thoth/papers/pdfs"
	@mkdir -p "$(OBSIDIAN_VAULT)/thoth/papers/markdown"
	@mkdir -p "$(OBSIDIAN_VAULT)/thoth/notes"
	@mkdir -p "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian"
	@echo "$(GREEN)✅ Directory structure created$(NC)"
	@if [ ! -f "$(OBSIDIAN_VAULT)/thoth/_thoth/settings.json" ]; then \
		if [ -f "templates/thoth.settings.json" ]; then \
			cp "templates/thoth.settings.json" "$(OBSIDIAN_VAULT)/thoth/_thoth/settings.json"; \
			echo "$(GREEN)✅ Full settings template deployed$(NC)"; \
		else \
			python3 -c "import json; json.dump({'version': '1.0.0', 'paths': {'workspace': 'thoth/_thoth', 'vault': '$(OBSIDIAN_VAULT)'}, 'apiKeys': {'openaiKey': '', 'anthropicKey': '', 'mistralKey': '', 'openrouterKey': ''}, 'servers': {'api': {'host': '0.0.0.0', 'port': 8000, 'autoStart': True}, 'mcp': {'host': 'localhost', 'port': 8001, 'autoStart': True, 'enabled': True}}}, open('$(OBSIDIAN_VAULT)/thoth/_thoth/settings.json', 'w'), indent=2)"; \
			echo "$(GREEN)✅ Default settings created$(NC)"; \
		fi; \
	else \
		echo "$(GREEN)✅ Settings preserved$(NC)"; \
	fi
	@if [ -d "data/prompts" ]; then \
		echo "$(YELLOW)Copying prompt templates (preserving existing)...$(NC)"; \
		find data/prompts -type f -name "*.j2" | while IFS= read -r file; do \
			rel_path=$${file#data/prompts/}; \
			dest="$(OBSIDIAN_VAULT)/thoth/_thoth/prompts/$$rel_path"; \
			mkdir -p "$$(dirname "$$dest")"; \
			if [ ! -f "$$dest" ]; then \
				cp "$$file" "$$dest" && echo "  ✓ Copied: $$rel_path"; \
			else \
				echo "  ○ Preserved: $$rel_path"; \
			fi; \
		done; \
		echo "$(GREEN)✅ Prompt templates processed$(NC)"; \
	fi
	@if [ ! -f "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian/mcp-plugins.json" ]; then \
		python3 -c "import json; json.dump({'version': '1.0.0', 'plugins': {'filesystem': {'enabled': False, 'name': 'Vault Files', 'description': 'Access files within the vault', 'transport': 'stdio', 'command': ['npx', '@modelcontextprotocol/server-filesystem', '{{obsidian_vault}}'], 'priority': 1, 'capabilities': ['tools'], 'sandbox': True, 'allowed_file_paths': ['{{obsidian_vault}}', '{{obsidian_vault}}/attachments']}, 'sqlite': {'enabled': False, 'name': 'Research DB', 'description': 'SQLite database for research', 'transport': 'stdio', 'command': ['npx', '@modelcontextprotocol/server-sqlite', '--db-path', '{{obsidian_vault}}/thoth/_thoth/research.db'], 'priority': 2, 'capabilities': ['tools'], 'sandbox': True}, 'git': {'enabled': False, 'name': 'Vault Git', 'description': 'Git operations for the vault', 'transport': 'stdio', 'command': ['npx', '@modelcontextprotocol/server-git', '--repository', '{{obsidian_vault}}'], 'priority': 3, 'capabilities': ['tools'], 'sandbox': True}}, 'vault_variables': {'obsidian_vault': '$(OBSIDIAN_VAULT)', 'vault_path': '$(OBSIDIAN_VAULT)', 'workspace': '$(OBSIDIAN_VAULT)/thoth/_thoth'}}, open('$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian/mcp-plugins.json', 'w'), indent=2)"; \
		echo "$(GREEN)✅ MCP plugins config created$(NC)"; \
	else \
		echo "$(GREEN)✅ MCP plugins config preserved$(NC)"; \
	fi
	@if [ ! -f "$(OBSIDIAN_VAULT)/.env.example" ]; then \
		echo "# Thoth Environment Configuration" > "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "THOTH_WORKSPACE_DIR=$(OBSIDIAN_VAULT)/.thoth" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "OBSIDIAN_VAULT_PATH=$(OBSIDIAN_VAULT)" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "MCP_PLUGIN_CONFIG_PATH=$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "# API Keys (copy to .env and fill in)" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "OPENAI_API_KEY=your_key_here" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "ANTHROPIC_API_KEY=your_key_here" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "BRAVE_API_KEY=your_key_here" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here" >> "$(OBSIDIAN_VAULT)/.env.example"; \
		echo "$(GREEN)✅ Environment template created$(NC)"; \
	else \
		echo "$(GREEN)✅ Environment template preserved$(NC)"; \
	fi

# =============================================================================
# RELEASE
# =============================================================================

.PHONY: release
release: ## Generate changelog from commits and version bump commands
	@bash scripts/release.sh $(VERSION)

# Set default target
.DEFAULT_GOAL := help

# =============================================================================
# Tailscale Serve Commands
# =============================================================================

.PHONY: tailscale-serve-reset
tailscale-serve-reset: ## Reset Tailscale serve configuration
	@echo "🔄 Resetting Tailscale serve..."
	sudo tailscale serve reset
	@echo "✅ Tailscale serve reset complete"

.PHONY: tailscale-serve-start
tailscale-serve-start: ## Start Tailscale serve for Letta (HTTPS on port 443)
	@echo "🚀 Starting Tailscale serve for Letta..."
	sudo tailscale serve --bg --https=443 8283
	@echo "✅ Tailscale serve started"
	@echo ""
	@echo "Available at: https://lambda-workstation.tail71634c.ts.net/"
	@echo ""
	@tailscale serve status

.PHONY: tailscale-serve-restart
tailscale-serve-restart: tailscale-serve-reset tailscale-serve-start ## Reset and restart Tailscale serve
	@echo "✅ Tailscale serve restarted"

.PHONY: tailscale-serve-status
tailscale-serve-status: ## Show Tailscale serve status
	@tailscale serve status

.PHONY: tailscale-serve-stop
tailscale-serve-stop: ## Stop Tailscale serve
	@echo "🛑 Stopping Tailscale serve..."
	sudo tailscale serve --https=443 off
	@echo "✅ Tailscale serve stopped"
