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

- Python 3.10+
- API Keys:
  - **Mistral API** (optional): For remote OCR conversion
  - **OpenRouter API**: For LLM analysis and agent
  - **OpenCitations** (optional): For citation metadata
  - **Semantic Scholar** (optional): For citation enrichment

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/project-thoth.git
   cd project-thoth
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   ```

3. **Configure environment**
   Create a `.env` file with your API keys:
   ```env
   # Required API Keys
   API_MISTRAL_KEY=your_mistral_key
   API_OPENROUTER_KEY=your_openrouter_key

   # Optional API Keys
   API_OPENCITATIONS_KEY=your_opencitations_key
   API_SEMANTICSCHOLAR_API_KEY=your_semanticscholar_key

   # LLM Configuration
   LLM_MODEL=openai/gpt-4o-mini
   CITATION_LLM_MODEL=openai/gpt-4
   RESEARCH_AGENT_LLM_MODEL=openai/gpt-4o-mini

   # API Server Configuration
   ENDPOINT_HOST=localhost
   ENDPOINT_PORT=8000
   ENDPOINT_BASE_URL=http://localhost:8000
   ```

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

# Project Thoth

Thoth is an academic PDF processing system that automatically analyzes PDF documents and generates structured notes.

## Features

- OCR conversion of PDF to Markdown
- LLM-based content analysis
- Citation extraction and processing
- Automatic note generation for Obsidian
- PDF directory monitoring for automatic processing
- Persistent file tracking to avoid reprocessing

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/project-thoth.git
   cd project-thoth
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

3. Create a `.env` file with your API keys:
   ```
   API_MISTRAL=your_mistral_api_key
   API_OPENROUTER=your_openrouter_api_key
   API_GOOGLE=your_google_api_key
   API_GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
   ```

## Usage

### PDF Monitor

The PDF monitor watches a directory for new PDF files and automatically processes them.

```bash
# Run the monitor with default settings
python -m thoth monitor

# Specify a custom directory to watch
python -m thoth monitor --watch-dir /path/to/pdf/directory

# Watch directory recursively
python -m thoth monitor --recursive

# Adjust polling interval (in seconds)
python -m thoth monitor --polling-interval 5.0

# Specify a custom tracking file (to maintain processing history)
python -m thoth monitor --track-file /path/to/tracking.json
```

#### Persistent File Tracking

The monitor keeps track of processed files in a JSON database file to avoid reprocessing files that have already been handled. This ensures that if you stop and restart the monitor, it won't process the same files again unless they've been modified.

By default, processed files are tracked in `output_dir/processed_pdfs.json`. You can specify a custom tracking file with the `--track-file` option.

The tracking system:
- Stores file metadata (size, modification time) to detect changes
- Preserves information about generated notes
- Uses atomic writes to prevent data corruption
- Automatically backs up corrupted tracking files

### Process a Single PDF

```bash
# Process a single PDF file
python -m thoth process /path/to/file.pdf
```

### Using the Python API

```python
from thoth.pipeline import ThothPipeline
from thoth.monitor import PDFMonitor
from pathlib import Path

# Process a single PDF
pipeline = ThothPipeline()
note_path = pipeline.process_pdf(Path("/path/to/file.pdf"))
print(f"Note created: {note_path}")

# Start the PDF monitor with persistent tracking
monitor = PDFMonitor(
    watch_dir=Path("/path/to/pdf/directory"),
    recursive=True,
    track_file=Path("/path/to/tracking.json")
)
monitor.start()
```

## Configuration

Configuration is managed through environment variables and the `.env` file. Key settings include:

- `pdf_dir`: Directory for PDF files (default: `data/pdf`)
- `notes_dir`: Directory for generated notes (default: `data/notes`)
- `markdown_dir`: Directory for Markdown files (default: `data/markdown`)
- `output_dir`: Directory for output files, including the default tracking file (default: `data/output`)

## License

[MIT License](LICENSE)

# Discovery System

The discovery system automatically finds and downloads research papers based on your interests:

```bash
# List configured sources
python -m thoth discovery list

# Create a new ArXiv source
python -m thoth discovery create --name "ml_papers" --type api --description "Machine learning papers"

# Run discovery
python -m thoth discovery run --source ml_papers --max-articles 10

# Start the scheduler for automatic discovery
python -m thoth discovery scheduler start
```

For detailed information about the discovery system, see [DISCOVERY_SYSTEM_README.md](DISCOVERY_SYSTEM_README.md).

## 📚 RAG Knowledge Base

Thoth includes a powerful RAG (Retrieval-Augmented Generation) system that allows you to search through and ask questions about your entire research collection:

### Setting Up RAG

```bash
# Index all your documents (run this after processing PDFs)
python -m thoth rag index

# Check RAG system status
python -m thoth rag stats
```

### Using RAG

```bash
# Search for relevant documents
python -m thoth rag search --query "transformer architecture" --k 5

# Ask questions about your research
python -m thoth rag ask --question "What are the main contributions of attention mechanisms in neural networks?"

# Filter searches by document type
python -m thoth rag search --query "deep learning" --filter-type note
```

### RAG in the Research Agent

The research agent has full access to the RAG system:

```bash
python -m thoth agent

# In the agent:
You: search my knowledge base for transformer papers
Agent: [searches and returns relevant papers]

You: what do my notes say about attention mechanisms?
Agent: [searches notes and provides summary]

You: explain the key differences between BERT and GPT based on my papers
Agent: [analyzes your collection and provides insights]
```

### RAG Configuration

Configure RAG in your `.env` file:

```env
# Embedding model for semantic search
RAG_EMBEDDING_MODEL="openai/text-embedding-3-small"

# Model for answering questions
RAG_QA_MODEL="openai/gpt-4o-mini"

# Chunk settings for document processing
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200

# Number of documents to retrieve for context
RAG_RETRIEVAL_K=4
```

## 🤖 Interactive Research Agent

## 🧩 Obsidian Plugin

A minimal plugin is provided in `obsidian-plugin/thoth-obsidian`. To build the plugin and load it into Obsidian:

1. Install dependencies and compile the TypeScript:
   ```bash
   cd obsidian-plugin/thoth-obsidian
   npm install
   npm run build
   ```
2. Copy the generated files (`manifest.json`, `main.js`, `styles.css`) to your Obsidian vault's `plugins/thoth-obsidian` folder.
3. Enable **Thoth Research Assistant** in Obsidian's community plugins settings.

Once enabled you can configure API keys and start the `thoth agent` process directly from Obsidian.
