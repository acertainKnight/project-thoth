# Thoth Research Assistant Documentation

Welcome to the comprehensive documentation for Thoth, an advanced AI-powered research assistant system designed for academic research, knowledge management, and intelligent document analysis.

## Quick Navigation

### Getting Started
- **[README](../README.md)** - Project overview and quick start guide
- **[Setup Guide](setup.md)** - Detailed installation and configuration instructions
- **[Usage Guide](usage.md)** - Comprehensive usage documentation and examples
- **[Letta Docker Setup](letta-docker-setup.md)** - Comprehensive Letta memory service Docker configuration

### System Architecture
- **[Architecture Overview](architecture.md)** - High-level system design and component interactions
- **[Services Documentation](services.md)** - Detailed service architecture and APIs
- **[Agent System](agent-system.md)** - Advanced agentic workflows and tool integration

### API Reference
- **[API Documentation](api.md)** - Complete REST API, WebSocket, and MCP protocol reference

## What is Thoth?

Thoth is a sophisticated research assistant that combines:

- **🤖 Advanced AI Agent**: LangGraph-powered research assistant with memory and tool orchestration
- **📚 Intelligent Document Processing**: Multi-stage pipelines for PDF analysis and knowledge extraction
- **🔍 Automated Discovery**: Multi-source paper discovery with quality evaluation
- **💬 Interactive Research Interface**: Obsidian plugin with real-time AI chat integration
- **⚡ Model Context Protocol**: 52 built-in MCP tools + VSCode-compatible 3rd party plugin system
- **🧠 Knowledge Management**: Dynamic knowledge graphs and semantic search capabilities
- **💾 Persistent Memory**: Letta-based memory system with cross-session persistence

## Key Capabilities

### For Researchers
- **Literature Discovery**: Automatically find and evaluate relevant papers from ArXiv, Semantic Scholar, and web sources
- **Citation Analysis**: Extract and analyze citation networks with relationship mapping
- **Interactive Querying**: Conversational interface for exploring your research corpus
- **Knowledge Synthesis**: AI-powered analysis and synthesis across multiple papers

### For Developers
- **Extensible Architecture**: Plugin-based system with clear service boundaries
- **Multi-Protocol Support**: REST API, WebSocket, and MCP integration
- **Modern AI Stack**: LangGraph agents, ChromaDB vectors, Pydantic schemas
- **Enterprise Features**: Health monitoring, caching, rate limiting, and async processing

### For Knowledge Workers
- **Obsidian Integration**: Seamless integration with your existing note-taking workflow
- **Multi-Chat Interface**: Manage multiple research conversations simultaneously
- **Automated Organization**: AI-powered tagging and content organization
- **Export Capabilities**: Export research data in multiple formats

## Architecture Highlights

### Service-Oriented Design
- **Microservice Architecture**: Loosely coupled services with clear responsibilities
- **Service Manager**: Central orchestration with dependency injection
- **Health Monitoring**: Comprehensive service health tracking and metrics

### Advanced AI Integration
- **Multi-Provider LLM Router**: Intelligent routing across OpenAI, Anthropic, Mistral, OpenRouter
- **RAG System**: ChromaDB-based vector search with semantic chunking
- **Structured Outputs**: Instructor-based LLM responses with Pydantic validation

### Research-Focused Features
- **Citation Graphs**: NetworkX-based relationship modeling
- **Discovery Engines**: Multi-source automated paper collection
- **Query Management**: Persistent research queries with evaluation metrics
- **Processing Pipelines**: Configurable document processing with extensible stages

## Documentation Structure

### For New Users
1. Start with the [README](../README.md) for a quick overview
2. Follow the [Setup Guide](setup.md) for installation and deployment options
3. Review the [Service Management Guide](service-management.md) for multi-service architecture
4. Explore the [Usage Guide](usage.md) for common workflows

### For Developers
1. Review the [Architecture Overview](architecture.md) for system design
2. Study the [Services Documentation](services.md) for detailed APIs
3. Examine the [Agent System](agent-system.md) for advanced features
4. Reference the [API Documentation](api.md) for integration details
5. Learn [Service Management](service-management.md) for deployment and scaling

### For Advanced Users
1. Understand the [Agent System](agent-system.md) for sophisticated workflows
2. Use the [API Documentation](api.md) for programmatic access
3. Customize services using the [Services Documentation](services.md)
4. Deploy with [Service Management](service-management.md) for production scaling

## Common Use Cases

### Academic Research

#### Quick Start (Recommended)
```bash
# One-command deployment to Obsidian vault
export OBSIDIAN_VAULT="/path/to/your/vault"
make deploy-and-start OBSIDIAN_VAULT="$OBSIDIAN_VAULT"

# This automatically:
# - Builds and deploys Obsidian plugin
# - Creates .thoth/ directory structure in vault
# - Copies all 22+ prompt templates
# - Starts all Docker services (API, MCP, ChromaDB, Letta, Discovery)
```

Services will be available at:
- API Server: http://localhost:8000
- MCP Server: http://localhost:8001  (52 tools)
- ChromaDB: http://localhost:8003
- Letta Memory: http://localhost:8283

#### Docker Management
```bash
# Check service status
make status

# View logs
make logs

# Restart services
make restart

# Stop services
make stop
```

### Knowledge Management
- **Obsidian Integration**: Real-time research chat within your notes
- **Multi-Chat Support**: Parallel research conversations on different topics
- **Knowledge Graphs**: Visual exploration of paper relationships
- **Export Options**: Multiple formats for downstream analysis

### Programmatic Access
```python
import requests

# Create a chat session
response = requests.post("http://localhost:8000/chat/sessions",
                        json={"title": "AI Research"})
session_id = response.json()["id"]

# Send a message
response = requests.post(f"http://localhost:8000/research/chat",
                        json={"message": "What are the latest attention mechanisms?",
                              "session_id": session_id})
```

## System Requirements

### Minimum Requirements
- Python 3.10+, Node.js 16+
- 4GB RAM, 2GB storage
- Linux, macOS, or Windows with WSL2

### Recommended Setup
- Python 3.12, Node.js 20+
- 16GB RAM, 10GB+ storage
- GPU support for local embeddings (optional)

## Support and Community

- **Issues**: [GitHub Issues](https://github.com/acertainKnight/project-thoth/issues)
- **Documentation**: [Project Wiki](https://github.com/acertainKnight/project-thoth/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/acertainKnight/project-thoth/discussions)

## License

MIT License - see [LICENSE](../LICENSE) file for details.

---

**Ready to get started?** Begin with the [Setup Guide](setup.md) or explore the [Usage Guide](usage.md) for detailed examples.
