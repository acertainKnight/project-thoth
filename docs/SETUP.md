# Thoth Setup Guide

This guide provides detailed instructions for setting up and configuring the Thoth Research Assistant system.

## System Requirements

### Minimum Requirements
- **Python**: 3.10 or higher (3.12 recommended)
- **Node.js**: 16.0 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space for installation and data
- **OS**: Linux, macOS, or Windows with WSL2

### Recommended Requirements
- **Python**: 3.12
- **Node.js**: 20.0 or higher
- **RAM**: 16GB for large document processing
- **Storage**: 10GB+ for document storage and vector databases
- **GPU**: Optional, for local embedding models

## Installation Methods

### Method 1: Quick Start (Recommended)

1. **Clone and Setup**
   ```bash
   git clone https://github.com/acertainKnight/project-thoth.git
   cd project-thoth

   # Check system dependencies
   make check-deps

   # Deploy everything
   make full-deploy
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Method 2: Manual Installation

#### Python Backend Setup

1. **Create Virtual Environment**
   ```bash
   # Using uv (fastest, recommended)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv sync

   # Or using traditional pip
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Verify Installation**
   ```bash
   python -m thoth --help
   ```

#### Obsidian Plugin Setup

1. **Install Dependencies**
   ```bash
   cd obsidian-plugin/thoth-obsidian
   npm install
   ```

2. **Build Plugin**
   ```bash
   npm run build
   ```

3. **Deploy to Obsidian**
   ```bash
   # Auto-detect Obsidian vault
   make deploy-plugin

   # Or specify vault location
   make deploy-plugin OBSIDIAN_VAULT="/path/to/your/vault"
   ```

4. **Enable in Obsidian**
   - Open Obsidian
   - Go to Settings → Community Plugins
   - Enable "Thoth Research Assistant"

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# === REQUIRED API KEYS ===
MISTRAL_API_KEY=your_mistral_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# === OPTIONAL API KEYS ===
# Citation and academic search
OPENCITATIONS_KEY=your_opencitations_key
SEMANTIC_SCHOLAR_KEY=your_semantic_scholar_key

# Web search capabilities
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_custom_search_engine_id
SERPER_API_KEY=your_serper_key

# === DIRECTORY CONFIGURATION ===
THOTH_WORKSPACE_DIR=/path/to/your/research/workspace
THOTH_PDF_DIR=/path/to/your/pdf/collection
THOTH_DATA_DIR=/path/to/thoth/data
THOTH_LOGS_DIR=/path/to/thoth/logs

# === SYSTEM CONFIGURATION ===
THOTH_LOG_LEVEL=INFO
THOTH_API_HOST=127.0.0.1
THOTH_API_PORT=8000

# === PERFORMANCE TUNING ===
TOKENIZERS_PARALLELISM=false
OMP_NUM_THREADS=1
```

### API Key Setup

#### Required Keys

1. **Mistral AI** (Primary LLM provider)
   - Sign up at [console.mistral.ai](https://console.mistral.ai)
   - Create API key
   - Add to `MISTRAL_API_KEY`

2. **OpenRouter** (Alternative LLM provider)
   - Sign up at [openrouter.ai](https://openrouter.ai)
   - Create API key
   - Add to `OPENROUTER_API_KEY`

#### Optional Keys

1. **OpenCitations** (Citation data)
   - Email [contact@opencitations.net](mailto:contact@opencitations.net) for API access
   - Add to `OPENCITATIONS_KEY`

2. **Semantic Scholar** (Academic paper metadata)
   - Apply at [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)
   - Add to `SEMANTIC_SCHOLAR_KEY`

3. **Google Custom Search** (Web search)
   - Create custom search engine at [cse.google.com](https://cse.google.com)
   - Get API key from [console.developers.google.com](https://console.developers.google.com)
   - Add `GOOGLE_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`

### Directory Structure Setup

Thoth will create the following directories automatically:

```
~/thoth-workspace/          # Main workspace (configurable)
├── data/                   # Vector stores and databases
├── knowledge/              # Knowledge graphs and processed data
├── logs/                   # Application logs
├── pdfs/                   # PDF document storage
├── queries/                # Saved research queries
└── prompts/               # Custom prompt templates
```

You can customize these locations in your `.env` file or through the Obsidian plugin settings.

## First Run

### 1. Start the Backend Services

```bash
# Start API server
make start-api

# Or start in development mode with auto-reload
make start-api-dev
```

The API server will be available at `http://localhost:8000`

### 2. Configure Obsidian Plugin

1. Open Obsidian
2. Open plugin settings: Settings → Community Plugins → Thoth Research Assistant
3. Configure essential settings:
   - **API Keys**: Enter your Mistral/OpenRouter keys
   - **Directories**: Set workspace and PDF directories
   - **Connection**: Verify endpoint (default: `http://127.0.0.1:8000`)

### 3. Test the Connection

1. Use the command palette (Ctrl/Cmd+P)
2. Run "Open Research Chat"
3. Send a test message: "Hello, are you working?"

### 4. Process Your First Documents

```bash
# Set up document monitoring
python -m thoth monitor --watch-dir /path/to/pdfs --optimized

# Index documents for RAG search
python -m thoth rag index

# Test RAG search
python -m thoth rag search --query "test query" --k 5
```

## Advanced Configuration

### MCP Integration Setup

For AI agent integration via Model Context Protocol:

```bash
# Start MCP server (stdio mode for CLI tools)
python -m thoth mcp stdio

# HTTP mode for web integration
python -m thoth mcp http --host localhost --port 8001
```

### Custom LLM Providers

Edit `src/thoth/utilities/config.py` to add custom LLM providers or modify model configurations.

### Performance Tuning

#### For Large Document Collections

```bash
# Increase memory limits
export THOTH_MAX_MEMORY=16GB
export CHROMA_MAX_BATCH_SIZE=500

# Use faster embedding models
export THOTH_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

#### For Slower Systems

```bash
# Reduce concurrent processing
export THOTH_MAX_CONCURRENT=2
export THOTH_CHUNK_SIZE=512

# Use smaller models
export THOTH_PRIMARY_MODEL=mistral/mistral-7b-instruct
```

### Development Mode

For development and debugging:

```bash
# Start both plugin watcher and API server
make dev

# Enable debug logging
export THOTH_LOG_LEVEL=DEBUG

# Run tests
pytest tests/
```

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors
```bash
# Ensure you're in the virtual environment
source .venv/bin/activate
pip install -e .
```

#### 2. Obsidian plugin not loading
```bash
# Rebuild and redeploy
make clean-plugin
make deploy-plugin
# Restart Obsidian
```

#### 3. API connection failures
```bash
# Check if services are running
make status

# Restart services
make stop-api
make start-api
```

#### 4. PDF processing failures
```bash
# Install additional dependencies
pip install "thoth[pdf]"

# Check PDF directory permissions
ls -la /path/to/pdf/directory
```

### Performance Issues

#### Slow processing
- Reduce batch sizes in `.env`
- Use faster embedding models
- Increase system RAM allocation

#### High memory usage
- Enable memory monitoring: `THOTH_ENABLE_MONITORING=true`
- Use smaller chunk sizes
- Process documents in smaller batches

### Getting Help

1. **Check logs**
   ```bash
   tail -f logs/thoth.log
   make logs
   ```

2. **Enable debug mode**
   ```bash
   export THOTH_LOG_LEVEL=DEBUG
   python -m thoth --help
   ```

3. **Report issues**
   - [GitHub Issues](https://github.com/acertainKnight/project-thoth/issues)
   - Include logs and system information
   - Describe steps to reproduce

## Next Steps

After successful setup:

1. **Read the [Usage Guide](USAGE.md)** for detailed feature documentation
2. **Explore [Examples](examples/)** for common research workflows
3. **Check [API Documentation](API.md)** for programmatic access
4. **Join the community** for support and feature discussions

---

*For additional help, see the [FAQ](FAQ.md) or create an issue on GitHub.*
