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
