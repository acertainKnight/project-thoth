# 🦉 Thoth - Research Assistant AI

Thoth is a production-ready AI-powered research assistant that automates the collection, analysis, and organization of academic literature. Named after the ancient Egyptian god of wisdom and knowledge, Thoth helps researchers efficiently manage their knowledge base and discover new insights.

## ✨ Key Features

### 📚 **Automated Paper Processing**
- **PDF Conversion**: Converts PDFs to markdown via Mistral OCR or a local fallback
- **Content Analysis**: Extracts key findings, methodology, results using LLMs
- **Citation Extraction**: Identifies and processes all references with metadata enrichment
- **Note Generation**: Creates structured Obsidian-compatible notes automatically

### 🔍 **Research Discovery & Filtering**
- **Multi-Source Discovery**: Automated paper discovery from ArXiv, PubMed, and custom sources
- **Smart Filtering**: AI-powered evaluation of papers against research queries
- **Scheduled Discovery**: Automated periodic searches for new relevant papers
- **Web Scraping**: Support for custom journal scraping with Chrome extension
- **Browser Emulator Recording**: Record login sessions and map elements on sites without APIs

### 🤖 **Interactive Research Agent**
- **Natural Language Interface**: Chat with your research collection
- **Query Management**: Create and manage research interests
- **Paper Analysis**: Find connections between papers and analyze research trends
- **Tool Integration**: Built on LangGraph with MCP framework

### 🔗 **Knowledge Management**
- **Citation Network**: Tracks relationships between papers in a graph structure
- **RAG System**: Vector search and question-answering over your collection
- **Tag Management**: Intelligent tag consolidation and suggestions
- **Obsidian Integration**: Seamless integration with Obsidian for note-taking

## 📋 Prerequisites

- **Python 3.10+** (Python 3.11+ recommended)
- **uv package manager** (for dependency management)
- **API Keys**:
  - **OpenRouter API** (required): For LLM analysis and agent - Get from [openrouter.ai](https://openrouter.ai)
  - **Mistral API** (optional): For remote OCR conversion - Get from [console.mistral.ai](https://console.mistral.ai)
  - **OpenCitations** (optional): For citation metadata
  - **Semantic Scholar** (optional): For citation enrichment

## 🚀 Installation

### **Quick Install (5 minutes)**

```bash
# 1. Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env with your OpenRouter API key (minimum required)

# 4. Test installation
uv run python health_check.py
```

### **🎯 Choose Your Setup Path**

- **📚 [Quick Start Paths](docs/QUICK_START_ENHANCED.md)** - Multiple 5-minute setup paths for different use cases
- **📋 [Command Reference](docs/COMMAND_REFERENCE_CARD.md)** - Essential commands cheat sheet

### **Complete Installation Options**

For detailed installation instructions including Docker, WSL, and development setups, see:

📖 **[Complete Installation Guide](docs/INSTALLATION_GUIDE.md)** - All installation methods and platforms

📖 **[Configuration Guide](docs/CONFIGURATION_GUIDE.md)** - Comprehensive configuration options

## 📖 Quick Start

### 1. Process a Single PDF
```bash
thoth process --pdf-path /path/to/paper.pdf
```

### 2. Start the PDF Monitor
Monitor a folder for new PDFs and process them automatically:
```bash
thoth monitor --watch-dir /path/to/pdfs --api-server
```

### 3. Chat with the Research Agent
```bash
thoth agent
```

Example conversation:
```
You: Create an ArXiv source for machine learning papers
Assistant: ✅ ArXiv Discovery Source Created Successfully!
...

You: What papers do I have on transformers?
Assistant: 🔍 I found 12 papers on transformers in your collection...
```

### 4. Index Your Knowledge Base
```bash
thoth rag index
```

### 5. Ask Questions About Your Research
```bash
thoth rag ask --question "What are the main contributions of the transformer architecture?"
```

## 🏗️ Architecture

### Service Layer Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Presentation   │     │      Agent      │     │       CLI       │
│   (Commands)    │     │  (LangGraph)    │     │   (Commands)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                         │
         └───────────────────────┴─────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    Service Manager      │
                    └────────────┬────────────┘
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     │                                                       │
┌────┴─────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──┴───────┐
│Processing│  │Discovery │  │   RAG    │  │Citation  │  │  Query   │
│ Service  │  │ Service  │  │ Service  │  │ Service  │  │ Service  │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Key Components

- **Pipeline**: Orchestrates the complete document processing workflow
- **Service Layer**: Centralized business logic for all operations
- **Citation Tracker**: Maintains the knowledge graph of paper relationships
- **Filter**: Evaluates papers against research queries
- **Agent**: Interactive assistant built with LangGraph

## 🛠️ Commands

### Document Processing
- `thoth process --pdf-path <path>` - Process a single PDF
- `thoth monitor` - Monitor directory for new PDFs
- `thoth reprocess-note --article-id <doi>` - Regenerate a note
- `thoth regenerate-all-notes` - Regenerate all notes

### Discovery & Filtering
- `thoth discovery list` - List all discovery sources
- `thoth discovery create --name <name> --type <api|scraper|emulator>` - Create source
- `thoth discovery run --source <name>` - Run discovery
- `thoth filter-test` - Test the filtering system

### Knowledge Base
- `thoth rag index` - Index all documents
- `thoth rag search --query <query>` - Search knowledge base
- `thoth rag ask --question <question>` - Ask questions
- `thoth rag stats` - Show RAG statistics

### Tag Management
- `thoth consolidate-tags` - Consolidate and suggest tags
- `thoth consolidate-tags-only` - Only consolidate existing tags
- `thoth suggest-tags` - Suggest new tags for articles

### Agent & API
- `thoth agent` - Start interactive agent chat
- `thoth api` - Start the API server

## 📂 Directory Structure

```
project-thoth/
├── data/
│   ├── pdf/              # Original PDF files
│   ├── markdown/         # OCR-converted markdown
│   ├── notes/            # Generated Obsidian notes
│   ├── agent/            # Agent-managed files
│   ├── discovery/        # Discovery configurations
│   ├── queries/          # Research queries
│   └── knowledge/        # Citation graph
├── src/
│   └── thoth/
│       ├── services/     # Service layer
│       ├── ingestion/    # Agent and filtering
│       ├── analyze/      # Analysis tools
│       ├── discovery/    # Discovery sources
│       ├── monitor/      # File monitoring
│       └── rag/          # RAG system
└── templates/            # Note templates
```

## 🔧 Configuration

The system uses a hierarchical configuration with environment variables:

```python
# Example configuration structure
THOTH_CONFIG = {
    'pdf_dir': 'data/pdf',
    'notes_dir': 'data/notes',
    'llm_config': {
        'model': 'openai/gpt-4o-mini',
        'temperature': 0.7,
        'max_tokens': 500000
    },
    'discovery_config': {
        'default_interval_minutes': 60,
        'default_max_articles': 50
    }
}
```

## 📊 API Endpoints

When running the API server (`thoth api`):

- `GET /download-pdf?url=<pdf_url>` - Download PDF for Obsidian
- `GET /view-markdown?path=<path>` - View markdown content
- `GET /health` - Health check endpoint

## 📚 RAG Knowledge Base

The RAG (Retrieval-Augmented Generation) system allows you to search through and ask questions about your entire research collection:

### Setting Up RAG
```bash
# Index all your documents (run this after processing PDFs)
thoth rag index

# Check RAG system status
thoth rag stats
```

### Using RAG
```bash
# Search for relevant documents
thoth rag search --query "transformer architecture" --k 5

# Ask questions about your research
thoth rag ask --question "What are the main contributions of attention mechanisms?"

# Filter searches by document type
thoth rag search --query "deep learning" --filter-type note
```

### RAG in the Research Agent
The research agent has full access to the RAG system:
```
You: search my knowledge base for transformer papers
Agent: [searches and returns relevant papers]

You: what do my notes say about attention mechanisms?
Agent: [searches notes and provides summary]
```

## 🧩 Extending Thoth

### Adding New Discovery Sources

```python
from thoth.discovery.api_sources import BaseAPISource

class CustomAPISource(BaseAPISource):
    def search(self, config, max_results=50):
        # Implement your API logic
        return articles
```

### Creating Custom Agent Tools

```python
from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool

class CustomTool(BaseThothTool):
    name = "custom_tool"
    description = "My custom research tool"

    def _run(self, query: str) -> str:
        # Tool logic here
        return result
```

## 🐛 Troubleshooting

### Common Issues

1. **OCR Failures**: Check Mistral API key and file size limits
2. **LLM Timeouts**: Adjust chunk sizes in configuration
3. **Discovery Errors**: Verify API keys and rate limits
4. **Import Errors**: Ensure proper installation with `pip install -e .`

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
thoth <command>
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [LangChain](https://langchain.com/) and [LangGraph](https://github.com/langchain-ai/langgraph)
- OCR optionally powered by [Mistral AI](https://mistral.ai/)
- LLMs via [OpenRouter](https://openrouter.ai/)
- Citation data from [OpenCitations](https://opencitations.net/) and [Semantic Scholar](https://semanticscholar.org/)

---

**Thoth**: *Transforming how researchers discover, analyze, and organize academic knowledge.*

## 📚 **Comprehensive Documentation**

This README provides a high-level overview. For detailed information, see our comprehensive documentation:

### **🚀 Getting Started**
- **[Installation Guide](docs/INSTALLATION_GUIDE.md)** - Complete installation for all platforms
- **[Configuration Guide](docs/CONFIGURATION_GUIDE.md)** - All configuration options and profiles
- **[Complete Feature Reference](docs/COMPLETE_FEATURE_REFERENCE.md)** - Every command and capability

### **🎯 For Users**
- **[Obsidian Plugin Guide](docs/OBSIDIAN_PLUGIN_README.md)** - Plugin installation and usage
- **[Obsidian Usage Guide](docs/OBSIDIAN_USAGE_GUIDE.md)** - Step-by-step usage instructions
- **[Obsidian Troubleshooting](docs/OBSIDIAN_TROUBLESHOOTING.md)** - Common issues and solutions

### **🔧 For Developers**
- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - Contributing and extending Thoth
- **[API Reference](docs/API_REFERENCE.md)** - FastAPI endpoint documentation
- **[Modern Agent Framework](docs/MODERN_AGENT_README.md)** - LangGraph-based architecture

### **🔍 Advanced Features**
- **[Discovery System](docs/DISCOVERY_SYSTEM_README.md)** - Automated paper discovery
- **[MCP Framework](docs/MCP_FRAMEWORK_README.md)** - Model Context Protocol
- **[Tag Consolidation](docs/TAG_CONSOLIDATION_README.md)** - Tag management system

### **🚀 Deployment**
- **[Docker Setup](docs/OBSIDIAN_DOCKER_SETUP.md)** - Containerized deployment
- **[WSL Setup](docs/OBSIDIAN_WSL_SETUP.md)** - Windows Subsystem for Linux
- **[Documentation Index](docs/README.md)** - Complete documentation navigation
