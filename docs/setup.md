# Thoth Setup Guide

Complete installation and configuration guide for Thoth Research Assistant.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Setup Wizard](#setup-wizard)
- [Manual Configuration](#manual-configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### One-Command Installation

**Linux/Mac:**
```bash
curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash
```

**Windows (WSL2):**
```powershell
# 1. Install WSL2 (PowerShell as Administrator, one-time)
wsl --install

# 2. Restart computer

# 3. Open Ubuntu terminal and run:
curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash
```

**What happens:**
1. Detects/installs Docker automatically
2. Runs interactive setup wizard
3. Installs `thoth` command to PATH
4. Optionally starts services immediately

**Time**: ~5 minutes

---

## Prerequisites

### Required

- **Python 3.12** (3.13 not yet supported)
  - Check: `python3 --version`
  - Install: [python.org](https://python.org)

- **Docker & Docker Compose**
  - Check: `docker --version && docker compose version`
  - Install: [docs.docker.com](https://docs.docker.com/get-docker/)

- **Obsidian** (optional, for plugin integration)
  - Download: [obsidian.md](https://obsidian.md/)

### Recommended

- **UV Package Manager**: Fast Python package installer
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### System Requirements

- **OS**: Linux, macOS, or Windows (WSL2)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 5GB free space
- **CPU**: Multi-core recommended

---

## Installation

### Method 1: Automated Install (Recommended)

The install script handles everything:

```bash
curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash
```

**Options:**
```bash
# Install specific version
bash install.sh --version 0.3.0-alpha.2

# Install latest alpha/pre-release
bash install.sh --alpha

# Install nightly build
bash install.sh --nightly

# List available versions
bash install.sh --list
```

### Method 2: Manual Install

For developers or custom setups:

```bash
# Clone repository
git clone https://github.com/acertainKnight/project-thoth.git
cd project-thoth

# Install dependencies
uv sync  # or: pip install -e ".[dev]"

# Install Playwright browsers (for discovery)
source .venv/bin/activate
python -m playwright install chromium

# Set vault path
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"

# Run setup wizard
python -m thoth setup
```

---

## Setup Wizard

The interactive setup wizard guides you through configuration.

### Wizard Flow

**1. Welcome Screen**
- Introduction and prerequisites check
- Navigation instructions

**2. Dependency Check**
- Verifies Docker installation
- Checks PostgreSQL (optional)
- Detects Letta service status
- Offers to install missing dependencies

**3. Vault Selection**
- Select your Obsidian vault directory
- Validates vault path
- Creates `_thoth/` directory if needed

**4. Letta Mode Selection**

Choose how to run agent memory:

**Option A: Letta Cloud** (easiest)
- Hosted service at app.letta.com
- Free tier available
- Just need API key
- No local infrastructure

**Option B: Self-Hosted** (full control)
- Local Docker container
- Works offline
- All data stays local
- ~500MB extra RAM

**5. API Keys Configuration**

Enter keys for LLM providers:
- **OpenAI** (required — embeddings): [platform.openai.com](https://platform.openai.com/)
- **OpenRouter** (required — backend LLM): [openrouter.ai/keys](https://openrouter.ai/keys)
- **Mistral AI** (required — PDF OCR extraction): [console.mistral.ai](https://console.mistral.ai/)
- **Semantic Scholar** (optional): [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)

**6. Model Selection**

Choose default models:
- **Analysis**: For research analysis (default: Claude 3.5 Sonnet via OpenRouter)
- **Generation**: For content generation (default: Mistral Large)
- **Embeddings**: For vector search (default: text-embedding-3-small)

**7. Deployment Mode**

Choose deployment architecture:
- **Local Mode**: All-in-one container (default, 1 container)
- **Microservices Mode**: Separate services (5 containers, advanced)

**8. Optional Features**

Enable additional capabilities:
- ✅ **RAG** (semantic search): Requires embeddings
- ✅ **Discovery** (automated paper finding): Requires browser automation
- ✅ **Advanced Citation Analysis**: Requires external APIs

**9. Configuration Review**

Review all settings before installation:
- Vault path
- Letta mode
- API keys (masked)
- Models
- Optional features

**10. Installation**

Wizard performs installation:
- Creates `settings.json`
- Generates Docker config
- Builds/pulls images
- Initializes database
- Deploys Obsidian plugin

**11. Completion**

- Success summary
- Next steps
- Quick start commands

---

## Manual Configuration

If you prefer to configure manually instead of using the wizard:

### 1. Create Settings File

```bash
mkdir -p "$OBSIDIAN_VAULT_PATH/thoth/_thoth"
cp templates/thoth.settings.json "$OBSIDIAN_VAULT_PATH/thoth/_thoth/settings.json"
```

### 2. Edit Settings

```json
{
  "api_keys": {
    "mistralKey": "your_key_here",
    "openrouterKey": "your_key_here"
  },
  "llm_config": {
    "default": {
      "model": "mistral/mistral-large-latest",
      "temperature": 0.7
    }
  },
  "memory": {
    "letta": {
      "mode": "self-hosted",
      "base_url": "http://localhost:8283"
    }
  }
}
```

### 3. Set Environment Variables

```bash
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"
export API_MISTRAL_KEY="your_key_here"
export API_OPENROUTER_KEY="your_key_here"
```

### 4. Start Services

```bash
# Development mode (hot-reload enabled)
make dev

# Production mode (optimized)
make prod
```

---

## Verification

### Check Services

```bash
# Health check all services
make health

# Expected output:
# ✓ API Server (8000/8080): healthy
# ✓ MCP Server (8082): healthy
# ✓ Letta (8283): healthy
# ✓ PostgreSQL: healthy
```

### Test API Connection

```bash
# Test API endpoint
curl http://localhost:8000/health | jq

# Test MCP server
curl http://localhost:8082/health | jq

# List MCP tools
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

### Test Document Processing

```bash
# Copy a test PDF to watch directory
cp test-paper.pdf "$OBSIDIAN_VAULT_PATH/thoth/papers/pdfs/"

# Check for generated note
ls "$OBSIDIAN_VAULT_PATH/thoth/notes/"

# View logs
tail -f "$OBSIDIAN_VAULT_PATH/thoth/_thoth/logs/thoth.log"
```

### Verify Plugin

1. Open Obsidian
2. Settings → Community Plugins
3. Check "Thoth Research Assistant" is enabled
4. Click Thoth icon in left sidebar
5. Should open chat interface

---

## Troubleshooting

### Docker Issues

**Port conflicts:**
```bash
# Check what's using ports
lsof -i :8000
lsof -i :8082
lsof -i :8283

# Stop conflicting services or edit ports in settings.json
```

**Permission errors:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Out of disk space:**
```bash
# Clean Docker system
docker system prune -a --volumes

# Check usage
docker system df
```

### Vault Detection Issues

**Error: "Could not detect vault"**

```bash
# Verify OBSIDIAN_VAULT_PATH is set
echo $OBSIDIAN_VAULT_PATH

# Should output your vault path, not empty

# Set it if not set
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"

# Or add to ~/.bashrc for persistence
echo 'export OBSIDIAN_VAULT_PATH="/path/to/your/vault"' >> ~/.bashrc
source ~/.bashrc
```

**Wrong vault detected:**
```bash
# Explicitly set the correct vault
export OBSIDIAN_VAULT_PATH="/correct/path/to/vault"

# Verify
python -c "from thoth.config import get_vault_root; print(get_vault_root())"
```

### Letta Connection Issues

**Letta not responding:**
```bash
# Check if Letta is running
docker ps | grep letta

# Start Letta if not running
docker compose -f docker-compose.letta.yml up -d

# Check Letta health
curl http://localhost:8283/v1/health

# View Letta logs
docker logs letta-server
```

**Agents not created:**
```bash
# Manually trigger agent initialization
python -c "
from thoth.services.agent_initialization_service import AgentInitializationService
service = AgentInitializationService()
service.initialize_all_agents()
"

# Verify agents exist
curl http://localhost:8283/v1/agents
```

### Plugin Issues

**Plugin not loading:**
1. Check plugin directory exists:
   ```bash
   ls "$OBSIDIAN_VAULT_PATH/.obsidian/plugins/thoth-obsidian/"
   ```
2. Verify files: `main.js`, `manifest.json`, `styles.css`
3. Disable "Restricted Mode" in Obsidian Settings
4. Enable "Thoth Research Assistant" in Community Plugins
5. Restart Obsidian

**Connection failed:**
1. Check backend is running: `make health`
2. Check plugin settings in Obsidian
3. Default: `http://localhost:8000`
4. For Docker: Use host IP or `http://host.docker.internal:8000`

### Hot-Reload Issues

**Settings changes not applying:**
1. Verify dev mode (not prod): `docker ps | grep dev`
2. Check logs: `make dev-logs`
3. Manual trigger: `make reload-settings`
4. Verify file path: `$OBSIDIAN_VAULT_PATH/thoth/_thoth/settings.json`

### Python Version Issues

**Error: "Python 3.13 not supported"**

Thoth requires Python 3.12 (3.13 has dependency incompatibilities):

```bash
# Check Python version
python3 --version

# Install Python 3.12 if needed (Ubuntu)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv

# Use specific version
python3.12 -m venv .venv
source .venv/bin/activate
```

---

## Next Steps

After successful installation:

1. **Start services**: `thoth start` (or `make dev` for development)
2. **Check health**: `make health`
3. **Open Obsidian**: Click Thoth icon to start chatting
4. **Read usage guide**: [usage.md](usage.md)
5. **Explore features**: Try paper discovery, Q&A, citation analysis

---

## Getting Help

- **Documentation**: [docs/](.) - All guides and references
- **GitHub Issues**: [Report a bug](https://github.com/acertainKnight/project-thoth/issues)
- **Logs**: `make dev-logs` or check `thoth/_thoth/logs/`
- **Health Check**: `make health` to diagnose service issues

---

**Setup Guide Version**: 3.0
**Last Updated**: February 2026
