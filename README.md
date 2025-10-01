# Thoth Research Assistant

An advanced AI-powered research assistant system designed for academic research paper processing, knowledge management, and intelligent document analysis. Thoth combines a powerful Python backend with an Obsidian plugin for seamless integration into research workflows.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache_2.0-green)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen)](CONTRIBUTING.md)

[Quick Start](#quick-start) • [Installation](#installation) • [Usage](#usage-examples) • [Contributing](#contributing)

## Why Thoth?

Thoth revolutionizes academic research by combining cutting-edge AI with intuitive knowledge management. Whether you're a researcher managing hundreds of papers, a student building literature reviews, or an academic seeking insights from document collections, Thoth provides intelligent automation for your research workflow.

**Key Benefits:**
- **Faster Analysis**: AI-powered paper summarization and analysis
- **Smart Integration**: Native Obsidian plugin with real-time sync
- **Multi-Source Discovery**: Automated paper discovery from ArXiv, Semantic Scholar, and more
- **Persistent Memory**: Advanced agent system with cross-session memory

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Quick Start

### Option 1: Docker (Recommended)
```bash
# Clone repository
git clone https://github.com/acertainKnight/project-thoth.git
cd project-thoth

# Configure your Obsidian vault path
export OBSIDIAN_VAULT="/path/to/your/obsidian/vault"

# One-command deployment (builds plugin + starts all services)
make deploy-and-start OBSIDIAN_VAULT="$OBSIDIAN_VAULT"
```

This will:
- ✅ Build and deploy the Obsidian plugin to your vault
- ✅ Create complete `.thoth/` directory structure with all prompts
- ✅ Start all services (API, MCP, ChromaDB, Letta, Discovery)
- ✅ Services available at: `http://localhost:8000` (API), `http://localhost:8001` (MCP)

### Option 2: Local Development
```bash
# Install dependencies (requires Python 3.10+)
uv venv && uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Deploy plugin and start services
make dev OBSIDIAN_VAULT="/path/to/vault"
```

### Docker Deployment

For containerized deployment:

```bash
# Development
make docker-init     # Initialize environment + local workspace
# Edit .env.docker with your API keys
make docker-dev      # Start development services

# Production
cp .env.prod.example .env.prod
make docker-prod     # Deploy production services

# Cloud Deployment
# See docs/cloud-deployment.md for AWS, GCP, Azure setup

# Management
make docker-status           # Check status of all environments
make docker-volumes          # Show persistent data volumes and sizes
make docker-shutdown         # Shutdown ALL services and clean up
make docker-shutdown-dev     # Shutdown only development services
make docker-shutdown-prod    # Shutdown only production services
make docker-shutdown-service SERVICE=<name> # Shutdown specific service

# Cleanup (increasing levels of deletion)
make docker-clean-cache      # Clean only build cache (safest)
make docker-clean            # Clean containers + unused images (preserves data)
make docker-clean-all        # Complete cleanup (WARNING: deletes data)

| Command | Build Cache | Containers | Images | Persistent Data |
|---------|-------------|------------|--------|-----------------|
| `docker-clean-cache` | ✅ Delete | ❌ Keep | ❌ Keep | ✅ **SAFE** |
| `docker-clean` | ✅ Delete | ✅ Delete | ⚠️ Unused only | ✅ **SAFE** |
| `docker-clean-all` | ✅ Delete | ✅ Delete | ✅ Delete | ⚠️ **DELETES** |

### 🔒 **Data Storage & Access**
Your valuable data is stored locally and can be watched in real-time:

#### **📁 Local Filesystem** (easily accessible)
- **Workspace**: `./workspace/` - PDFs, notes, processed documents
- **Application Data**: `./data/` - Embeddings, outputs, citations
- **Logs**: `./logs/` - Application logs for monitoring
- **Cache**: `./cache/` - Temporary cache files

#### **🗄️ Database Volumes** (Docker-managed)
- **Knowledge Base**: ChromaDB vectors → `thoth-chroma-data` volume
- **Memory System**: Letta data → `thoth-letta-data` + `thoth-letta-postgres` volumes

#### **👁️ Real-Time Monitoring**
```bash
# Watch files being created/processed
tail -f logs/*.log
ls -la workspace/data/
find workspace -name '*.pdf' -newer yesterday
```

**✅ SAFE commands** (`docker-clean-cache`, `docker-clean`) preserve ALL your data
**⚠️ DANGER command** (`docker-clean-all`) requires confirmation and deletes everything
```

Services will be available at:
- API Server: http://localhost:8000
- MCP Server: http://localhost:8001
- ChromaDB: http://localhost:8003
- Letta Server: http://localhost:8283

## Key Features

### Advanced AI System
- **52 MCP Tools**: Complete research assistant toolkit (100% functional)
- **3rd Party MCP Plugins**: VSCode-compatible plugin system for extending capabilities
- **Multi-Provider LLM Router**: Intelligent routing across OpenAI, Anthropic, Mistral, OpenRouter
- **Persistent Memory**: Letta-based with salience retention and cross-session persistence
- **MCP Framework**: Full Model Context Protocol with HTTP/stdio/SSE transports

### Intelligent Agent System
- **Dynamic Agent Creation**: `"create an agent that analyzes citation patterns"`
- **@Agent Interactions**: `"@citation-analyzer analyze this paper's references"`
- **Specialized Agent Types**: Research, Analysis, Discovery, Citation, and Synthesis agents
- **Tool Auto-Assignment**: Agents automatically receive appropriate tools based on their purpose
- **Memory Persistence**: Agents maintain context and knowledge across sessions

### Document Processing
- **Multi-Stage Pipelines**: Configurable processing with extensible stages
- **Citation Analysis**: Advanced extraction with network analysis capabilities
- **Semantic Chunking**: Context-preserving intelligent text segmentation
- **Metadata Enrichment**: Automated extraction of academic metadata and relationships

### Research Discovery
- **Multi-Source Integration**: ArXiv, Semantic Scholar, and web search
- **Chrome Extension Bridge**: Real-time paper collection from browser
- **Automated Scheduling**: Background discovery with configurable intervals
- **Source Evaluation**: Pre-download relevance scoring and filtering

## Architecture

Thoth uses a service-oriented architecture with the `ServiceManager` as the central orchestrator:

```mermaid
graph TD
    A[ThothOrchestrator] --> B[Service Manager]
    A --> C[SubagentFactory]
    A --> D[LettaToolRegistry]

    C --> E[Letta Server]
    D --> E

    B --> F[LLM Router]
    B --> G[RAG System]
    B --> H[Discovery Engine]
    B --> I[Pipeline Processor]

    J[Obsidian Plugin] --> K[API Server]
    K --> A
    K --> B

    L[CLI Interface] --> M[MCP Server]
    M --> B

    N[External APIs] --> H
    O[Vector Store] --> G
    P[Agent Memory] --> E
```

### Core Components

**Python Backend** (`src/thoth/`)
- **Service Architecture**: Microservice-based with centralized ServiceManager
- **Pipeline System**: Modular, extensible document processing stages
- **Agent System**: LangGraph-powered with persistent memory
- **API Layer**: FastAPI server with REST + WebSocket support
- **MCP Integration**: Full Model Context Protocol implementation
- **CLI Tools**: Comprehensive command-line interface

**Obsidian Plugin** (`obsidian-plugin/thoth-obsidian/`)
- **Multi-Chat Interface**: Concurrent research conversations
- **Real-time Sync**: Live WebSocket connection to backend
- **Settings Panel**: Complete configuration management
- **Note Integration**: Direct interaction with vault files
- **Auto-updates**: Hot reload during development

**Technology Stack**: Python, FastAPI, LangGraph, TypeScript, Obsidian, ChromaDB

## Installation

### Prerequisites
- Python 3.10-3.12
- Obsidian (for plugin integration)
- uv (recommended) or pip

### Quick Installation

```bash
# Clone repository
git clone https://github.com/acertainKnight/project-thoth.git
cd project-thoth

# Install with uv (recommended)
uv venv && uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Configure API keys
echo "MISTRAL_API_KEY=your_key_here" > .env
echo "OPENROUTER_API_KEY=your_key_here" >> .env

# Deploy to Obsidian and start services
make dev
```

### API Keys

| Service | Required | Purpose |
|---------|----------|---------|
| Mistral | Yes | Primary LLM provider |
| OpenRouter | Yes | LLM fallback |
| OpenAI | No | Alternative LLM |
| Semantic Scholar | No | Paper discovery |

Get keys from: [Mistral Console](https://console.mistral.ai/), [OpenRouter](https://openrouter.ai/keys)

## Usage Examples

### Interactive Research Session
```bash
# Start the research agent
python -m thoth agent

# Start with specific research focus
python -m thoth agent research --query "transformer architectures"
```

### Document Processing
```bash
# Process single PDF
python -m thoth pdf process /path/to/paper.pdf

# Batch process directory
python -m thoth pdf process /path/to/papers/ --parallel

# Monitor directory with real-time processing
python -m thoth monitor --watch-dir ./papers --optimized
```

### Multi-Source Discovery
```bash
# Start discovery service
python -m thoth discovery start

# Search specific sources
python -m thoth discovery search "large language models" --source arxiv
python -m thoth discovery search "neural networks" --source semantic_scholar
```

### Intelligent Agent System
```bash
# Create specialized agents through chat
"create an agent that analyzes citation patterns in research papers"
"make a discovery agent for machine learning papers"
"build an agent that helps with reference formatting"

# Interact with created agents using @mentions
"@citation-analyzer analyze the references in this paper"
"@ml-discovery find recent papers about transformer attention mechanisms"
"@reference-formatter format these citations in APA style"

# List and manage your agents
"list my agents"
"show available agents"
```

**Agent Types:**
- **Research**: General research assistance and literature reviews
- **Analysis**: Deep document analysis and critical evaluation
- **Discovery**: Multi-source paper finding and monitoring
- **Citation**: Citation extraction and bibliography management
- **Synthesis**: Knowledge integration and summary generation

### Development Commands

| Command | Purpose |
|---------|---------|
| `make deploy-and-start` | Complete deployment + start all services |
| `make deploy-plugin` | Deploy Obsidian plugin only |
| `make start` | Start all Docker services |
| `make stop` | Stop all services |
| `make restart` | Restart all services |
| `make status` | Check service health |
| `make logs` | View service logs |
| `make dev` | Start with live reload |
| `make clean` | Clean build artifacts |

## Configuration

### Environment Variables

| Category | Variable | Purpose | Required |
|----------|----------|---------|----------|
| AI | `MISTRAL_API_KEY` | Primary LLM provider | Yes |
| AI | `OPENROUTER_API_KEY` | LLM fallback/alternatives | Yes |
| AI | `OPENAI_API_KEY` | OpenAI models | No |
| Discovery | `SEMANTIC_SCHOLAR_KEY` | Academic paper metadata | No |
| Discovery | `GOOGLE_API_KEY` | Web search capabilities | No |
| Data | `OPENCITATIONS_KEY` | Citation data access | No |
| System | `THOTH_WORKSPACE_DIR` | Main working directory | No |
| System | `THOTH_PDF_DIR` | PDF storage location | No |
| Agents | `LETTA_SERVER_URL` | Letta server connection | No |
| Agents | `LETTA_ENABLE_AGENT_SYSTEM` | Enable agent orchestration | No |
| Agents | `LETTA_MAX_AGENTS_PER_USER` | Agent limit per user | No |

### Directory Structure

All configuration and data is stored in your Obsidian vault:

```
vault/
├── .thoth/
│   ├── data/
│   │   ├── prompts/          # 22+ AI prompt templates
│   │   ├── pdfs/            # Original documents
│   │   ├── notes/           # Generated notes
│   │   ├── knowledge/       # Citation graphs
│   │   ├── queries/         # Saved queries
│   │   ├── agents/          # Agent configurations
│   │   └── discovery/       # Discovery results
│   ├── cache/               # Temporary cache
│   ├── logs/                # Application logs
│   └── config/              # Configuration files
│
├── .obsidian/plugins/thoth/
│   ├── main.js                 # Plugin code
│   ├── manifest.json           # Plugin metadata
│   └── mcp-plugins.json       # 3rd party MCP configuration
│
└── .thoth.settings.json        # Main settings
```

## Development

### Project Structure
```
project-thoth/
├── src/thoth/              # Python package
│   ├── cli/               # Command-line interface
│   ├── services/          # Core services
│   │   ├── llm/          # Multi-provider LLM
│   │   ├── service_manager.py  # Central orchestrator
│   │   └── ...
│   ├── ingestion/
│   │   └── agent_v2/     # Modern agent system
│   ├── mcp/              # MCP server + tools
│   │   ├── server.py     # MCP server
│   │   ├── tools/        # 52 built-in tools
│   │   ├── plugin_manager.py  # 3rd party plugins
│   │   └── validation.py      # Plugin validation
│   ├── memory/           # Letta integration
│   ├── pipelines/        # Document processing
│   ├── rag/              # Vector retrieval
│   └── server/           # FastAPI server
│
├── obsidian-plugin/       # Obsidian integration
│   └── thoth-obsidian/
│       ├── src/          # TypeScript source
│       └── main.ts       # Entry point
│
├── docker/               # Docker configurations
│   ├── api/
│   ├── mcp/
│   └── discovery/
│
├── templates/            # File templates
├── Makefile             # Build commands (streamlined)
└── docker-compose.dev.yml  # Docker services
```

### Testing
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src/thoth tests/

# Run specific test categories
pytest tests/services/            # Service layer tests
pytest tests/agent_v2/            # Agent system tests
pytest tests/integration/         # Integration tests
```

### Code Quality
```bash
# Linting and formatting
uv run ruff check            # Check code quality
uv run ruff format           # Format code
uv run pytest               # Run tests
```

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following our style guide
4. Test your changes: `pytest tests/`
5. Commit your changes: `git commit -m "Add amazing feature"`
6. Push to your branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## Advanced Features

### Multi-Agent Intelligence
- **Specialized Research Agents**: Dedicated agents for literature review, citation analysis, and concept extraction
- **Agent Orchestration**: Intelligent coordination between agents for complex research workflows
- **Memory Sharing**: Cross-agent knowledge sharing for comprehensive analysis

### Knowledge Graph Integration
- **Automatic Relationship Extraction**: AI-powered discovery of connections between papers and concepts
- **Visual Knowledge Mapping**: Interactive graph visualization of research relationships
- **Graph-Based Queries**: Semantic search through connected knowledge structures

### Performance & Scale
- **Async Processing**: Concurrent operations for handling multiple documents simultaneously
- **Smart Caching**: Intelligent caching of embeddings, analysis results, and API responses
- **Memory Management**: Efficient handling of large document collections and knowledge bases

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

---

**Thoth** - Empowering research through intelligent automation and AI-assisted knowledge management.
