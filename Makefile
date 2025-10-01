# =============================================================================
# Thoth Research Assistant - Streamlined Makefile
# =============================================================================

# Configuration Variables
OBSIDIAN_VAULT ?= /mnt/c/Users/nghal/Documents/Obsidian Vault
PLUGIN_SRC_DIR = obsidian-plugin/thoth-obsidian
PLUGIN_DEST_DIR = $(OBSIDIAN_VAULT)/.obsidian/plugins/thoth-obsidian

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
	@echo "  $(GREEN)deploy-and-start$(NC)     Deploy plugin + start complete ecosystem"
	@echo "  $(GREEN)deploy-plugin$(NC)        Deploy plugin with vault integration"
	@echo "  $(GREEN)start$(NC)                Start complete Thoth ecosystem"
	@echo "  $(GREEN)stop$(NC)                 Stop all Thoth services"
	@echo "  $(GREEN)status$(NC)               Check status of all services"
	@echo ""
	@echo "$(YELLOW)🔧 Development:$(NC)"
	@echo "  $(GREEN)dev$(NC)                  Plugin development mode (watch + rebuild)"
	@echo "  $(GREEN)logs$(NC)                 View service logs"
	@echo "  $(GREEN)clean$(NC)                Clean build artifacts"
	@echo ""
	@echo "$(YELLOW)📚 Knowledge Base:$(NC)"
	@echo "  $(GREEN)rebuild-kb$(NC)           Rebuild entire knowledge base"
	@echo "  $(GREEN)agent$(NC)                Start interactive research agent"
	@echo ""
	@echo "$(YELLOW)🔍 Diagnostics:$(NC)"
	@echo "  $(GREEN)check-vault$(NC)          Check vault integration status"
	@echo "  $(GREEN)check-deps$(NC)           Check required dependencies"
	@echo ""
	@echo "$(YELLOW)Configuration:$(NC)"
	@echo "  OBSIDIAN_VAULT=$(OBSIDIAN_VAULT)"
	@echo ""
	@echo "$(YELLOW)Example:$(NC)"
	@echo '  make deploy-and-start OBSIDIAN_VAULT="/path/to/your/vault"'

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
	@make start
	@echo ""
	@echo "$(GREEN)✅ COMPLETE SETUP FINISHED!$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "1. Configure API keys: $(OBSIDIAN_VAULT)/.thoth.settings.json"
	@echo "2. Enable MCP plugins: $(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json"
	@echo "3. Reload Obsidian: Ctrl/Cmd+P → 'Reload app'"
	@echo "4. Start researching! 🧠"

.PHONY: deploy-plugin
deploy-plugin: _check-vault _build-plugin ## Deploy Obsidian plugin with complete vault integration
	@echo "$(YELLOW)Deploying plugin with vault integration...$(NC)"
	@mkdir -p "$(PLUGIN_DEST_DIR)"
	@cp -r $(PLUGIN_SRC_DIR)/dist/* "$(PLUGIN_DEST_DIR)/"
	@cp $(PLUGIN_SRC_DIR)/manifest.json "$(PLUGIN_DEST_DIR)/"
	@cp $(PLUGIN_SRC_DIR)/styles.css "$(PLUGIN_DEST_DIR)/" 2>/dev/null || true
	@make _setup-vault-integration OBSIDIAN_VAULT="$(OBSIDIAN_VAULT)"
	@echo "$(GREEN)✅ Plugin deployment complete!$(NC)"

# =============================================================================
# SERVICE MANAGEMENT
# =============================================================================

.PHONY: start
start: ## Start complete Thoth ecosystem (Letta + ChromaDB + API + MCP)
	@echo "$(YELLOW)Starting Thoth ecosystem...$(NC)"
	@docker compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✅ Services started:$(NC)"
	@echo "  • API Server: http://localhost:8080"
	@echo "  • MCP Server: http://localhost:8081"
	@echo "  • ChromaDB: http://localhost:8003"
	@echo "  • Letta Memory: http://localhost:8283"

.PHONY: stop
stop: ## Stop all Thoth services
	@echo "$(YELLOW)Stopping Thoth services...$(NC)"
	@docker compose -f docker-compose.dev.yml down
	@echo "$(GREEN)✅ All services stopped$(NC)"

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
# DEVELOPMENT
# =============================================================================

.PHONY: dev
dev: ## Plugin development mode (watch + auto-rebuild)
	@echo "$(YELLOW)Starting plugin development mode...$(NC)"
	@echo "$(YELLOW)Plugin will auto-rebuild on file changes$(NC)"
	@cd $(PLUGIN_SRC_DIR) && npm install
	@cd $(PLUGIN_SRC_DIR) && npm run watch

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
	@if [ -d "$(OBSIDIAN_VAULT)/.thoth/data/prompts" ] && [ -n "$$(find '$(OBSIDIAN_VAULT)/.thoth/data/prompts' -name '*.j2' 2>/dev/null)" ]; then echo "$(GREEN)✅$(NC)"; else echo "$(RED)❌$(NC)"; fi
	@echo ""
	@if [ -d "$(OBSIDIAN_VAULT)/.thoth/data/prompts" ]; then \
		echo "Prompt templates: $$(find '$(OBSIDIAN_VAULT)/.thoth/data/prompts' -name '*.j2' 2>/dev/null | wc -l)"; \
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
	@mkdir -p "$(OBSIDIAN_VAULT)/.thoth/data"/{pdfs,markdown,notes,knowledge,queries,agents,discovery,prompts}
	@mkdir -p "$(OBSIDIAN_VAULT)/.thoth"/{cache,logs,config}
	@mkdir -p "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth"
	@echo "$(GREEN)✅ Directory structure created$(NC)"
	@if [ ! -f "$(OBSIDIAN_VAULT)/.thoth.settings.json" ]; then \
		if [ -f ".thoth.settings.json" ]; then \
			cp ".thoth.settings.json" "$(OBSIDIAN_VAULT)/.thoth.settings.json"; \
			echo "$(GREEN)✅ Settings copied to vault$(NC)"; \
		else \
			python3 -c "import json; json.dump({'version': '1.0.0', 'paths': {'workspace': '$(OBSIDIAN_VAULT)/.thoth', 'vault': '$(OBSIDIAN_VAULT)'}, 'apiKeys': {'openaiKey': '', 'anthropicKey': '', 'mistralKey': '', 'openrouterKey': ''}, 'servers': {'api': {'host': '0.0.0.0', 'port': 8000, 'autoStart': True}, 'mcp': {'host': 'localhost', 'port': 8001, 'autoStart': True, 'enabled': True}}}, open('$(OBSIDIAN_VAULT)/.thoth.settings.json', 'w'), indent=2)"; \
			echo "$(GREEN)✅ Default settings created$(NC)"; \
		fi; \
	else \
		echo "$(GREEN)✅ Settings preserved$(NC)"; \
	fi
	@if [ -d "data/prompts" ]; then \
		echo "$(YELLOW)Copying prompt templates (preserving existing)...$(NC)"; \
		find data/prompts -type f -name "*.j2" | while IFS= read -r file; do \
			rel_path=$${file#data/prompts/}; \
			dest="$(OBSIDIAN_VAULT)/.thoth/data/prompts/$$rel_path"; \
			mkdir -p "$$(dirname "$$dest")"; \
			if [ ! -f "$$dest" ]; then \
				cp "$$file" "$$dest" && echo "  ✓ Copied: $$rel_path"; \
			else \
				echo "  ○ Preserved: $$rel_path"; \
			fi; \
		done; \
		echo "$(GREEN)✅ Prompt templates processed$(NC)"; \
	fi
	@if [ ! -f "$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json" ]; then \
		python3 -c "import json; json.dump({'version': '1.0.0', 'plugins': {'filesystem': {'enabled': False, 'name': 'Vault Files', 'description': 'Access files within the vault', 'transport': 'stdio', 'command': ['npx', '@modelcontextprotocol/server-filesystem', '{{obsidian_vault}}'], 'priority': 1, 'capabilities': ['tools'], 'sandbox': True, 'allowed_file_paths': ['{{obsidian_vault}}', '{{obsidian_vault}}/attachments']}, 'sqlite': {'enabled': False, 'name': 'Research DB', 'description': 'SQLite database for research', 'transport': 'stdio', 'command': ['npx', '@modelcontextprotocol/server-sqlite', '--db-path', '{{obsidian_vault}}/.thoth/research.db'], 'priority': 2, 'capabilities': ['tools'], 'sandbox': True}, 'git': {'enabled': False, 'name': 'Vault Git', 'description': 'Git operations for the vault', 'transport': 'stdio', 'command': ['npx', '@modelcontextprotocol/server-git', '--repository', '{{obsidian_vault}}'], 'priority': 3, 'capabilities': ['tools'], 'sandbox': True}}, 'vault_variables': {'obsidian_vault': '$(OBSIDIAN_VAULT)', 'vault_path': '$(OBSIDIAN_VAULT)', 'workspace': '$(OBSIDIAN_VAULT)/.thoth'}}, open('$(OBSIDIAN_VAULT)/.obsidian/plugins/thoth/mcp-plugins.json', 'w'), indent=2)"; \
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

# Set default target
.DEFAULT_GOAL := help
