# Thoth Setup Guide

Comprehensive installation and configuration guide for Thoth Research Assistant.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
  - [Docker Installation (Recommended)](#docker-installation-recommended)
  - [Local Installation](#local-installation)
- [Configuration](#configuration)
- [Obsidian Plugin Setup](#obsidian-plugin-setup)
- [API Keys](#api-keys)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python**: 3.10, 3.11, or 3.12 (NOT 3.13)
  - Check version: `python --version`
  - [Download Python](https://www.python.org/downloads/)

- **Docker & Docker Compose**: For containerized deployment
  - Check Docker: `docker --version`
  - Check Compose: `docker compose version`
  - [Install Docker](https://docs.docker.com/get-docker/)

- **Obsidian**: For plugin integration
  - [Download Obsidian](https://obsidian.md/)

- **UV Package Manager**: Recommended for Python dependencies
  - Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Or use pip as fallback

### System Requirements

- **OS**: Linux, macOS, or Windows (WSL2 recommended for Windows)
- **RAM**: 8GB minimum, 16GB recommended
- **Disk**: 10GB free space (for Docker images and data)
- **CPU**: Multi-core recommended for parallel processing

## Installation Methods

### Docker Installation (Recommended)

Docker provides the easiest setup with all dependencies pre-configured.

#### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/acertainKnight/project-thoth.git
cd project-thoth

# Check repository structure
ls -la
```

#### Step 2: Set Environment Variables

```bash
# Set your Obsidian vault path
export OBSIDIAN_VAULT_PATH="/path/to/your/obsidian/vault"

# Verify it's set
echo $OBSIDIAN_VAULT_PATH
```

**Important**: The vault path must:
- Be an absolute path (not relative)
- Point to your Obsidian vault root directory
- Contain a `_thoth/` subdirectory (will be created if missing)

#### Step 3: Configure API Keys

```bash
# Copy example environment file
cp .env.example .env

# Edit with your preferred editor
nano .env  # or vim, code, etc.
```

Add your API keys to `.env`:
```bash
# Required keys
MISTRAL_API_KEY=your_mistral_key_here
OPENROUTER_API_KEY=your_openrouter_key_here

# Optional keys
OPENAI_API_KEY=your_openai_key_here
SEMANTIC_SCHOLAR_KEY=your_semantic_scholar_key_here
```

#### Step 4: Start Development Environment

> **📘 Letta Memory System**: Thoth uses Letta as a standalone memory service. The first time you run `make dev`, it will automatically:
> 1. Create `.env.letta` from `.env.letta.example` (if it doesn't exist)
> 2. Check if Letta is running
> 3. Prompt to start Letta if not running
> 4. Connect Thoth to Letta
>
> See [LETTA_SETUP.md](./LETTA_SETUP.md) for detailed information.

```bash
# Start all services with hot-reload (automatically starts Letta if needed)
make dev

# First-time users: This will:
# 1. Create .env.letta from example (if needed)
# 2. Check if Letta is running
# 3. Prompt to start Letta
# 4. Build Docker images
# 2. Start 8 services (API, MCP, Monitor, Agent, Discovery, Letta, PostgreSQL, ChromaDB)
# 3. Deploy Obsidian plugin
# 4. Initialize databases
```

#### Step 5: Verify Services

```bash
# Check all services are running
make health

# Expected output:
# API Server: ✓ Running on port 8000
# MCP Server: ✓ Running on port 8082 (HTTP transport with /mcp and /sse endpoints)
# Letta: ✓ Running on port 8283
# PostgreSQL: ✓ Running
# ChromaDB: ✓ Running on port 8003
```

### Local Installation

For development without Docker:

#### Step 1: Install Python Dependencies

```bash
# Clone repository
git clone https://github.com/acertainKnight/project-thoth.git
cd project-thoth

# Create virtual environment with UV (recommended)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
uv sync

# Or with pip (slower)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test]"
```

#### Step 2: Install Playwright

Required for browser-based discovery features:

```bash
# Install Playwright browsers
python -m playwright install chromium

# Verify installation
python -m playwright --version
```

#### Step 3: Set Up PostgreSQL

Letta requires PostgreSQL with pgvector extension:

```bash
# Install PostgreSQL and pgvector
# Ubuntu/Debian:
sudo apt-get install postgresql-15 postgresql-15-pgvector

# macOS with Homebrew:
brew install postgresql@15
brew install pgvector

# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql@15  # macOS

# Create database for Letta
createdb letta
psql letta -c "CREATE EXTENSION vector;"
```

#### Step 4: Configure Environment

```bash
# Set vault path
export OBSIDIAN_VAULT_PATH="$HOME/Documents/ObsidianVault"

# Configure API keys
cp .env.example .env
# Edit .env with your keys
```

#### Step 5: Start Services Manually

```bash
# Terminal 1: Start API server
python -m thoth server start --port 8000

# Terminal 2: Start MCP server
python -m thoth mcp start --port 8000

# Terminal 3: Start Letta
letta server --port 8283
```

## Configuration

### Vault Structure

Thoth uses a vault-centric configuration approach. All settings and data are stored in your Obsidian vault under `_thoth/`:

```
your-vault/
├── _thoth/
│   ├── settings.json          # Main configuration (hot-reloadable)
│   ├── data/
│   │   ├── pdfs/             # Place PDF files here
│   │   ├── notes/            # Generated notes appear here
│   │   ├── knowledge/        # Citation graphs
│   │   └── prompts/          # Custom AI prompts
│   ├── logs/
│   │   ├── thoth.log         # Application logs
│   │   └── letta.log         # Agent system logs
│   └── cache/                # Temporary cache files
```

### Settings File

The `_thoth/settings.json` file controls all Thoth configuration:

```json
{
  "llm_config": {
    "default": {
      "model": "mistral/mistral-large-latest",
      "temperature": 0.7,
      "max_tokens": 4096
    },
    "analysis": {
      "model": "openrouter/anthropic/claude-3.5-sonnet",
      "temperature": 0.3,
      "max_tokens": 8192
    }
  },
  "discovery": {
    "auto_start_scheduler": false,
    "default_max_articles": 50,
    "default_interval_minutes": 1440
  },
  "rag": {
    "embedding_model": "all-MiniLM-L6-v2",
    "chunk_size": 500,
    "chunk_overlap": 50
  }
}
```

**Hot-Reload**: In development mode (`make dev`), changes to `settings.json` are automatically applied within ~2 seconds!

### Directory Configuration

By default, Thoth uses these paths (relative to vault root):

```json
{
  "directories": {
    "pdf": "_thoth/data/pdfs",
    "notes": "_thoth/data/notes",
    "knowledge": "_thoth/data/knowledge",
    "prompts": "_thoth/data/prompts",
    "logs": "_thoth/logs",
    "cache": "_thoth/cache"
  }
}
```

Paths can be:
- **Relative**: `_thoth/data/pdfs` (relative to vault root)
- **Absolute**: `/absolute/path/to/directory`

## Obsidian Plugin Setup

### Automatic Installation (via Make)

```bash
# Deploy plugin to Obsidian
make deploy-plugin
```

This copies the plugin to `.obsidian/plugins/thoth-obsidian/` in your vault.

### Manual Installation

1. **Build the plugin**:
   ```bash
   cd obsidian-plugin/thoth-obsidian
   npm install
   npm run build
   ```

2. **Copy to Obsidian**:
   ```bash
   mkdir -p "$OBSIDIAN_VAULT_PATH/.obsidian/plugins/thoth-obsidian"
   cp main.js manifest.json styles.css \
      "$OBSIDIAN_VAULT_PATH/.obsidian/plugins/thoth-obsidian/"
   ```

3. **Enable in Obsidian**:
   - Open Obsidian
   - Settings → Community Plugins
   - Turn off "Restricted Mode"
   - Enable "Thoth Research Assistant"

### Plugin Configuration

After enabling the plugin:

1. **Click the Thoth ribbon icon** (left sidebar) or use Command Palette (`Ctrl/Cmd+P` → "Thoth")
2. **Open Settings**: Settings → Thoth Research Assistant
3. **Configure connection**:
   - **Local Mode**: Use `http://localhost:8000` (default)
   - **Remote Mode**: Set custom URL for Docker deployments

4. **Test connection**: Click "Test Connection" button

## API Keys

### Required Keys

#### Mistral AI
- **Purpose**: Primary LLM provider for analysis and generation
- **Get Key**: [Mistral Console](https://console.mistral.ai/)
- **Free Tier**: Limited tokens per month
- **Recommended Models**:
  - `mistral-large-latest`: Best quality
  - `mistral-medium-latest`: Good balance
  - `mistral-small-latest`: Fast and cheap

#### OpenRouter
- **Purpose**: Access to multiple LLM providers (Anthropic, OpenAI, etc.)
- **Get Key**: [OpenRouter](https://openrouter.ai/keys)
- **Free Tier**: Limited requests
- **Benefits**: Automatic fallback, model routing, unified API

### Optional Keys

#### OpenAI
- **Purpose**: Access to GPT models
- **Get Key**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **Cost**: Pay-per-use pricing

#### Semantic Scholar
- **Purpose**: Enhanced paper discovery and metadata
- **Get Key**: [Semantic Scholar API](https://www.semanticscholar.org/product/api)
- **Free Tier**: 5000 requests/5 minutes

#### Google Search
- **Purpose**: Web search for paper discovery
- **Get Key**: [Google Cloud Console](https://console.cloud.google.com/)
- **Requirements**: Enable Custom Search API

### Configuring Keys

**Option 1: Environment Variables** (recommended for local development):
```bash
export MISTRAL_API_KEY="your_key"
export OPENROUTER_API_KEY="your_key"
```

**Option 2: .env File** (recommended for Docker):
```bash
# .env file in project root
MISTRAL_API_KEY=your_key
OPENROUTER_API_KEY=your_key
```

**Option 3: Settings JSON** (not recommended - security risk):
```json
{
  "api_keys": {
    "mistral_key": "your_key",
    "openrouter_key": "your_key"
  }
}
```

## Verification

### Check Services

```bash
# Health check all services
make health

# Or check manually:
curl http://localhost:8000/health | jq
curl http://localhost:8082/health | jq
curl http://localhost:8283/v1/health | jq
```

### Test API

```bash
# Test API endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Thoth!"}'

# Test MCP tools
curl http://localhost:8082/tools | jq
```

### Test Document Processing

```bash
# Process a test PDF
python -m thoth pdf process test.pdf

# Check output
ls -la "$OBSIDIAN_VAULT_PATH/_thoth/data/notes/"
```

### View Logs

```bash
# Development logs (all services)
make dev-logs

# Specific service logs
docker logs thoth-dev-api
docker logs thoth-dev-mcp
docker logs thoth-dev-letta

# Application logs in vault
tail -f "$OBSIDIAN_VAULT_PATH/_thoth/logs/thoth.log"
```

## Troubleshooting

### Common Issues

#### Port Already in Use

**Symptom**: Error binding to port 8000/8082/8283

**Solution**:
```bash
# Find process using port
lsof -i :8000
# Kill the process
kill -9 <PID>

# Or use different ports in settings.json
```

#### Docker Permission Errors

**Symptom**: Permission denied errors in Docker containers

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or run with sudo (not recommended)
sudo make dev
```

#### Vault Not Detected

**Symptom**: `ValueError: Could not detect vault`

**Solution**:
```bash
# Ensure OBSIDIAN_VAULT_PATH is set
echo $OBSIDIAN_VAULT_PATH

# Should point to valid directory
ls -la "$OBSIDIAN_VAULT_PATH"

# Create _thoth directory if missing
mkdir -p "$OBSIDIAN_VAULT_PATH/_thoth"
```

#### Plugin Not Loading in Obsidian

**Symptom**: Plugin doesn't appear in Obsidian

**Solution**:
1. Check plugin directory exists:
   ```bash
   ls "$OBSIDIAN_VAULT_PATH/.obsidian/plugins/thoth-obsidian/"
   ```
2. Verify files are present: `main.js`, `manifest.json`, `styles.css`
3. Disable "Restricted Mode" in Obsidian settings
4. Enable plugin in Community Plugins section
5. Restart Obsidian

#### Hot-Reload Not Working

**Symptom**: Settings changes not applied

**Solution**:
1. Verify dev mode: `docker ps` should show `thoth-dev-*` containers
2. Check settings.json location: `$OBSIDIAN_VAULT_PATH/_thoth/settings.json`
3. Watch logs: `make dev-logs`
4. Manual reload: `make reload-settings`

#### Test Failures

**Symptom**: `pytest` tests failing

**Solution**:
```bash
# Update dependencies
uv sync

# Clear pytest cache
pytest --cache-clear

# Run with verbose output
pytest -vv tests/
```

### Getting Help

- **Check Logs**: `make dev-logs` or `tail -f _thoth/logs/thoth.log`
- **GitHub Issues**: [Report an issue](https://github.com/acertainKnight/project-thoth/issues)
- **Documentation**: See other docs in this directory
- **Health Check**: `make health` to verify all services

## Next Steps

After successful installation:

1. **Read the [Usage Guide](usage.md)** for day-to-day operations
2. **Check the [Architecture](architecture.md)** to understand the system
3. **See [Quick Reference](quick-reference.md)** for command cheat sheet
4. **Try processing your first paper** with the Obsidian plugin!

---

**Need help?** Open an issue on [GitHub](https://github.com/acertainKnight/project-thoth/issues) or check the [Troubleshooting](#troubleshooting) section above.
