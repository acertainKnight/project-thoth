# Thoth Research Assistant

Thoth is an advanced AI-powered research assistant system designed for academic research paper processing, knowledge management, and intelligent document analysis. The system combines a powerful Python backend with an Obsidian plugin for seamless integration into research workflows.

## Overview

Thoth provides a comprehensive suite of tools for researchers, academics, and knowledge workers:

- **🔍 Intelligent PDF Processing**: Automatically extract, analyze, and summarize academic papers
- **🤖 AI-Powered Analysis**: Advanced LLM integration for document understanding and knowledge extraction
- **📚 Knowledge Management**: Build and maintain searchable knowledge graphs from research materials
- **🔗 Citation Discovery**: Automated citation extraction and academic source validation
- **💬 Interactive Chat Interface**: Converse with your research corpus through AI-powered chat
- **🌐 Web Integration**: Discover and process academic papers from web sources
- **📝 Obsidian Integration**: Seamless integration with Obsidian for note-taking and knowledge management
- **⚡ MCP Protocol Support**: Modern Context Protocol for AI agent interoperability

## Architecture

### Core Components

**Python Backend (`src/thoth/`)**
- **Pipeline System**: Modular document processing pipelines
- **Service Layer**: Microservice architecture for scalable operations
- **MCP Server**: Model Context Protocol implementation for AI agent integration
- **API Server**: FastAPI-based REST API and WebSocket support
- **CLI Interface**: Comprehensive command-line tools

**Obsidian Plugin (`obsidian-plugin/thoth-obsidian/`)**
- **Multi-Chat Interface**: Multiple concurrent research conversations
- **Real-time Integration**: Live connection to Thoth backend services
- **Settings Management**: Comprehensive configuration interface
- **Document Integration**: Direct interaction with Obsidian notes and files

### Key Features

#### Advanced Agent System
- **LangGraph-powered Research Assistant**: Modern agentic workflow with memory and tool orchestration
- **Multi-Tool Integration**: Comprehensive toolkit for research tasks with automatic tool selection
- **Conversation Memory**: Persistent context across research sessions
- **MCP Framework Integration**: Full Model Context Protocol support for AI agent interoperability

#### Sophisticated Document Processing
- **Multi-Stage Pipeline**: Configurable document processing with extensible stages
- **Citation Graph Analysis**: Advanced citation extraction with network analysis
- **Semantic Chunking**: Intelligent text segmentation preserving context
- **Metadata Enrichment**: Automated extraction of academic metadata and relationships

#### Enterprise-Grade AI Integration
- **Multi-Provider LLM Router**: Intelligent routing based on task type and cost optimization
- **Advanced RAG System**: ChromaDB-based vector store with semantic search
- **Structured Output Processing**: Instructor-based LLM responses with Pydantic validation
- **Token Usage Tracking**: Comprehensive monitoring and cost management

#### Research Discovery Engine
- **Multi-Source Discovery**: ArXiv, Semantic Scholar, web search integration
- **Chrome Extension Bridge**: Real-time paper collection from browser
- **Automated Scheduling**: Background discovery with configurable intervals
- **Source Evaluation**: Pre-download relevance scoring and filtering

#### Knowledge Management
- **Dynamic Knowledge Graphs**: NetworkX-based relationship modeling
- **Tag Consolidation**: AI-powered tag hierarchy and organization
- **Query Management**: Persistent research queries with evaluation metrics
- **Cross-Reference Analysis**: Connection discovery between papers and concepts

## Quick Start

### Prerequisites

- Python 3.10-3.12
- Node.js 16+ (for Obsidian plugin)
- Obsidian (for plugin integration)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/acertainKnight/project-thoth.git
   cd project-thoth
   ```

2. **Set up Python environment**
   ```bash
   # Using uv (recommended)
   uv venv
   uv sync

   # Or using pip
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Configure API keys**
   Create a `.env` file with your API keys:
   ```bash
   MISTRAL_API_KEY=your_mistral_key
   OPENROUTER_API_KEY=your_openrouter_key
   # Add other optional keys as needed
   ```

4. **Deploy Obsidian Plugin**
   ```bash
   make deploy-plugin
   # Or specify custom vault location:
   make deploy-plugin OBSIDIAN_VAULT="/path/to/your/vault"
   ```

5. **Start the services**
   ```bash
   # Start API server
   make start-api

   # Or start both plugin watcher and API server
   make dev
   ```

### Development Workflow

**Quick Commands via Makefile:**
```bash
make help              # Show all available commands
make check-deps        # Verify required dependencies
make deploy-plugin     # Build and deploy Obsidian plugin
make start-api         # Start Thoth API server
make dev               # Start development mode (plugin + API)
make status            # Check service status
make clean             # Clean build artifacts
```

**Manual Commands:**
```bash
# CLI interface
python -m thoth --help

# Start specific services
python -m thoth api --host 0.0.0.0 --port 8000
python -m thoth mcp stdio
python -m thoth agent research --query "machine learning"

# Process documents
python -m thoth pdf process /path/to/papers/
python -m thoth discovery start
```

## Configuration

### Environment Variables

Thoth uses environment variables and configuration files for setup:

```bash
# Core API Keys
MISTRAL_API_KEY=           # Primary LLM provider
OPENROUTER_API_KEY=        # Alternative LLM provider

# Optional Services
OPENCITATIONS_KEY=         # Citation data access
GOOGLE_API_KEY=           # Web search capabilities
SEMANTIC_SCHOLAR_KEY=     # Academic paper metadata

# System Configuration
THOTH_WORKSPACE_DIR=      # Main working directory
THOTH_PDF_DIR=           # PDF storage location
THOTH_DATA_DIR=          # Data and cache directory
```

### Directory Structure

```
project-thoth/
├── src/thoth/              # Python package
│   ├── cli/               # Command-line interface
│   ├── services/          # Core services
│   ├── mcp/              # MCP protocol implementation
│   ├── server/           # API server
│   ├── pipelines/        # Document processing
│   ├── rag/              # RAG implementation
│   └── utilities/        # Helper modules
├── obsidian-plugin/       # Obsidian integration
│   └── thoth-obsidian/   # Plugin source code
├── Makefile              # Development commands
└── pyproject.toml        # Python project configuration
```

## Usage Examples

### Research Workflow

1. **Start the API server**
   ```bash
   # Start the Obsidian API server
   python -m thoth api --host 127.0.0.1 --port 8000

   # Or use the Makefile
   make start-api
   ```

2. **Interactive research session**
   ```bash
   # Start interactive agent chat
   python -m thoth agent
   ```

3. **Document monitoring and processing**
   ```bash
   # Monitor PDF directory with API server
   python -m thoth monitor --watch-dir ./papers --api-server --optimized

   # Process specific PDF
   python -m thoth locate-pdf "paper title or DOI"
   ```

4. **Advanced research through Obsidian**
   - Ensure API server is running (`make start-api`)
   - Open Obsidian → Use Ctrl/Cmd+P → "Open Research Chat"
   - Multi-chat support for different research topics
   - Real-time connection to your knowledge base

5. **MCP integration**
   ```bash
   # Start MCP server for CLI integration
   python -m thoth mcp stdio

   # HTTP MCP server
   python -m thoth mcp http --host localhost --port 8000
   ```

### MCP Integration

Thoth implements the Model Context Protocol for seamless AI agent integration:

```bash
# Start MCP server for CLI tools
python -m thoth mcp stdio

# HTTP server for web integration
python -m thoth mcp http --host localhost --port 8000
```

### API Usage

The REST API provides programmatic access to all Thoth capabilities:

```python
import requests

# Start a chat session
response = requests.post("http://localhost:8000/chat/sessions",
                        json={"title": "Research Session"})

# Send a message
requests.post(f"http://localhost:8000/chat/sessions/{session_id}/messages",
              json={"message": "Summarize recent ML papers"})
```

## Advanced Features

### Knowledge Graph Integration
- Automatic relationship extraction from documents
- Graph-based query capabilities
- Visual knowledge mapping

### Multi-Agent Architecture
- Specialized agents for different research tasks
- Agent coordination and memory sharing
- Extensible agent framework

### Performance Optimization
- Async processing for concurrent operations
- Caching and request optimization
- Memory management for large document collections

## Development

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

### Code Quality

The project uses modern Python tooling:
- **Ruff**: Fast Python linter and formatter
- **Black**: Code formatting
- **pytest**: Testing framework
- **pre-commit**: Git hooks for code quality

```bash
# Run code quality checks
uv run ruff check
uv run ruff format
uv run pytest
```

### Architecture Extensions

Thoth is designed for extensibility:
- **Plugin System**: Add custom document processors
- **Service Integration**: Connect to external APIs and databases
- **Transport Layers**: Support for various communication protocols
- **LLM Providers**: Easy integration of new language models

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/acertainKnight/project-thoth/issues)
- **Documentation**: [Project Wiki](https://github.com/acertainKnight/project-thoth/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/acertainKnight/project-thoth/discussions)

---

**Thoth** - Empowering research through intelligent automation and AI-assisted knowledge management.
