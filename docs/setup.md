# Thoth Setup Guide

This guide provides detailed instructions for setting up and configuring the Thoth Research Assistant system, including options for single-service deployment and multi-service architectures.

## Deployment Architecture Options

Thoth can be deployed in several configurations:

1. **🏠 Single Container** - All services in one container (simple development)
2. **🏗️ Multi-Service** - Separate containers for each service (recommended)
3. **☁️ Cloud/Kubernetes** - Scalable microservice deployment
4. **🧠 Memory-First** - Letta memory service with other services connecting to it

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

### Method 1: Multi-Service Deployment (Recommended for Production)

This method deploys each service separately for maximum scalability and fault isolation.

1. **Clone and Setup**
   ```bash
   git clone https://github.com/acertainKnight/project-thoth.git
   cd project-thoth

   # Check system dependencies
   make check-deps
   ```

2. **Configure All Services**
   ```bash
   # Main application configuration
   cp .env.example .env
   # Edit .env with your API keys

   # Memory service configuration
   cp deployment/letta-memory-service/.env.example deployment/letta-memory-service/.env
   # Edit with Letta-specific settings
   ```

3. **Start All Services**
   ```bash
   # Development environment (all services)
   ./scripts/start-all-services.sh dev

   # Production environment (all services)
   ./scripts/start-all-services.sh prod

   # Check status
   ./scripts/start-all-services.sh status
   ```

4. **Service URLs**
   - **Main API**: http://localhost:8000
   - **MCP Server**: http://localhost:8001
   - **Memory Service**: http://localhost:8283
   - **Vector Database**: http://localhost:8003
   - **Monitoring**: http://localhost:9090 (Prometheus), http://localhost:3000 (Grafana)

### Method 2: Individual Service Setup

Start only the services you need for development or testing.

#### Core Services (Minimum Required)
```bash
# 1. Start memory service (Letta)
cd deployment/letta-memory-service
make start

# 2. Start vector database
docker-compose up -d chromadb

# 3. Start main chat agent
make docker-up-dev
```

#### Optional Services
```bash
# Start monitoring stack
docker-compose -f docker/monitoring/docker-compose.monitoring.yml --profile monitoring up -d

# Start discovery service (if running separately)
python -m thoth discovery server
```

#### Using Service-Specific Commands
```bash
# Use the service management Makefile
make -f Makefile.services help              # Show all options

# Start specific services
make -f Makefile.services start-memory      # Memory service only
make -f Makefile.services start-chat        # Chat agent only
make -f Makefile.services start-monitoring  # Monitoring only

# Start service combinations
make -f Makefile.services start-core        # Memory + Vector DB
make -f Makefile.services start-app         # Chat + Discovery
make -f Makefile.services start-full        # Everything + Monitoring
```

### Method 3: Quick Start (Single Container)

For simple development and testing.

1. **Clone and Setup**
   ```bash
   git clone https://github.com/acertainKnight/project-thoth.git
   cd project-thoth

   # Check system dependencies
   make check-deps

   # Deploy everything in single container
   make full-deploy
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

### Method 4: Manual Installation

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

## First Run Options

### Option A: Multi-Service Architecture (Recommended)

This starts all services separately for better scaling and fault isolation.

#### 1. Start All Services
```bash
# Development environment (with hot-reload)
./scripts/start-all-services.sh dev

# Production environment (optimized)
./scripts/start-all-services.sh prod

# Check all services are healthy
./scripts/start-all-services.sh status
```

#### 2. Service URLs Available
- **Main API**: http://localhost:8000
- **MCP Server**: http://localhost:8001
- **Memory Service (Letta)**: http://localhost:8283
- **Vector Database**: http://localhost:8003
- **Monitoring**: http://localhost:9090 (Prometheus), http://localhost:3000 (Grafana)

#### 3. Individual Service Management
```bash
# Start only specific services
make -f Makefile.services start-memory      # Memory service
make -f Makefile.services start-chat        # Chat agent
make -f Makefile.services start-monitoring  # Monitoring

# Check service health
make -f Makefile.services health-check

# View service logs
make -f Makefile.services logs-memory
make -f Makefile.services logs-chat
```

### Option B: Single Service (Simple Development)

#### 1. Start the Backend Services

```bash
# Start API server (traditional method)
make start-api

# Or start in development mode with auto-reload
make start-api-dev
```

The API server will be available at `http://localhost:8000`

## Configure Obsidian Plugin

1. Open Obsidian
2. Open plugin settings: Settings → Community Plugins → Thoth Research Assistant
3. Configure essential settings:
   - **API Keys**: Enter your Mistral/OpenRouter keys
   - **Directories**: Set workspace and PDF directories
   - **Connection**: Verify endpoint (default: `http://127.0.0.1:8000`)

## Test Your Setup

### 1. Health Check All Services
```bash
# Check all services (multi-service setup)
make -f Makefile.services health-check

# Or check individual services
curl http://localhost:8000/health    # Main API
curl http://localhost:8283/health    # Memory service
curl http://localhost:8003/api/v1/heartbeat  # Vector DB
```

### 2. Test the Chat Agent
```bash
# Interactive agent (works with any setup)
python -m thoth agent

# Or via Obsidian
# 1. Use command palette (Ctrl/Cmd+P)
# 2. Run "Open Research Chat"
# 3. Send test message: "Hello, are you working?"
```

### 3. Test Memory Integration
```bash
# Test Letta memory integration
python scripts/test_memory_mcp_integration.py

# Test memory tools via agent
python -m thoth agent
# In chat: "Use memory_health_check to verify the memory system"
```

### 4. Process Your First Documents

```bash
# Set up document monitoring (works with any setup)
python -m thoth monitor --watch-dir /path/to/pdfs --optimized

# Index documents for RAG search
python -m thoth rag index

# Test RAG search
python -m thoth rag search --query "test query" --k 5
```

## Advanced Configuration

### Service-Specific Configuration

#### Memory Service (Letta) Configuration
```bash
# Edit memory service settings
nano deployment/letta-memory-service/.env

# Key settings:
LETTA_SERVER_URL=http://localhost:8283
LETTA_DB_PASSWORD=secure_password
LETTA_POOL_SIZE=50
LETTA_ARCHIVAL_MEMORY_ENABLED=true
LETTA_FALLBACK_ENABLED=true
```

#### Main Application Configuration
```bash
# Edit main application settings
nano .env

# Key settings for service integration:
LETTA_SERVER_URL=http://localhost:8283  # Connect to memory service
THOTH_CHROMADB_URL=http://localhost:8003  # Connect to vector DB
API_OPENROUTER_KEY=your_key
API_MISTRAL_KEY=your_key
```

### MCP Integration Setup

The MCP server is automatically started with the main application:

```bash
# MCP server starts automatically with chat service
# Available at: http://localhost:8001

# For standalone MCP server:
python -m thoth mcp stdio    # CLI integration
python -m thoth mcp http     # HTTP integration
```

### Letta Memory System Setup

The memory system runs as a separate service:

```bash
# Start Letta memory service
cd deployment/letta-memory-service
make start

# Check memory service health
make health

# View memory service logs
make logs

# Test memory integration
python scripts/test_memory_mcp_integration.py
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

### Multi-Service Setup Issues

#### 1. Service Won't Start
```bash
# Check Docker and service status
./scripts/start-all-services.sh status

# Check specific service logs
make -f Makefile.services logs-memory    # Memory service
make -f Makefile.services logs-chat      # Chat service

# Restart specific service
docker-compose restart thoth-chat
```

#### 2. Memory Service Connection Issues
```bash
# Check if Letta is running
curl http://localhost:8283/health

# Check memory service logs
cd deployment/letta-memory-service
make logs

# Restart memory service
make restart
```

#### 3. Port Conflicts
```bash
# Check what's using the ports
netstat -tulpn | grep :8283  # Memory service
netstat -tulpn | grep :8000  # Main API
netstat -tulpn | grep :8001  # MCP server

# Kill conflicting processes
sudo fuser -k 8283/tcp
```

#### 4. Service Health Check Failures
```bash
# Run comprehensive health check
make -f Makefile.services health-check

# Check individual service health
curl http://localhost:8000/health    # Main API
curl http://localhost:8283/health    # Memory service
curl http://localhost:8003/api/v1/heartbeat  # Vector DB

# Restart unhealthy services
make -f Makefile.services restart-all
```

### Traditional Setup Issues

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
# Check if services are running (multi-service)
./scripts/start-all-services.sh status

# Or check traditional setup
make status

# Restart services
./scripts/stop-all-services.sh
./scripts/start-all-services.sh dev
```

#### 4. PDF processing failures
```bash
# Install additional dependencies
pip install "thoth[pdf]"

# Check PDF directory permissions
ls -la /path/to/pdf/directory

# Test with optimized processing
python -m thoth monitor --watch-dir /path/to/pdfs --optimized
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

1. **Read the [Usage Guide](usage.md)** for detailed feature documentation
2. **Explore [Examples](examples/)** for common research workflows
3. **Check [API Documentation](api.md)** for programmatic access
4. **Join the community** for support and feature discussions

---

*For additional help, see the [FAQ](faq.md) or create an issue on GitHub.*
