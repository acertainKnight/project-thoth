# Thoth AI Research Agent

Thoth is an autonomous research assistant that helps researchers manage academic literature by creating an interconnected knowledge base.

## Overview

Thoth builds a core PDF processing pipeline with Obsidian integration. The initial version:

1. Monitors a designated folder for new PDF files
2. Processes PDFs using OCR to convert them to Markdown
3. Generates structured Obsidian notes from the Markdown content
4. Extracts and processes citations with custom URIs
5. Creates a citation-based linking system between notes

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/thoth.git
   cd thoth
   ```

2. Create a virtual environment using UV:
   ```bash
   # Install UV if you don't have it
   pip install uv

   # Create and activate virtual environment
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   uv pip install -e .
   ```

4. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

5. Edit the `.env` file with your configuration and API keys:
   ```
   # Base Configuration
   WORKSPACE_DIR=/path/to/your/workspace
   PDF_DIR=${WORKSPACE_DIR}/data/pdfs
   MARKDOWN_DIR=${WORKSPACE_DIR}/data/markdown
   NOTES_DIR=${WORKSPACE_DIR}/data/notes
   TEMPLATES_DIR=${WORKSPACE_DIR}/templates
   LOG_LEVEL=INFO
   LOG_FILE=${WORKSPACE_DIR}/logs/thoth.log

   # API Keys
   API_MISTRAL_KEY=your_mistral_key
   API_OPENROUTER_KEY=your_openrouter_key

   # File monitoring
   WATCH_INTERVAL=5
   BULK_PROCESS_CHUNK_SIZE=10
   ```

## Usage

### Running Thoth

Start Thoth to monitor your PDF folder:

```bash
python -m thoth
```

Thoth will:
1. Initialize all components
2. Process any existing PDFs in your PDF folder
3. Start monitoring for new PDFs
4. Handle URI requests when citations are clicked in Obsidian

### Setting Up Obsidian

1. Create or open an Obsidian vault
2. Set your `NOTES_DIR` in the `.env` file to point to a folder within your Obsidian vault
3. Configure Obsidian to handle custom URIs:
   - In Obsidian settings, go to "Core Plugins" and enable "URI"
   - On Windows, you may need to register the `thoth://` URI scheme with your system

### Workflow

1. **Adding Research Papers**:
   - Place PDF files in your configured `PDF_DIR` folder
   - Thoth will automatically process them and create notes in your Obsidian vault

2. **Exploring Citations**:
   - When viewing a note in Obsidian, you'll see citations with links
   - Clicking on a citation link will either:
     - Navigate to an existing note if the cited paper is already processed
     - Trigger Thoth to download and process the cited paper if it's not in your library

3. **Discovering Related Papers**:
   - Thoth maintains bidirectional links between papers
   - You can see which papers cite a particular paper and which papers it cites

### URI Handling

Thoth uses custom URIs to handle citation links. When you click on a citation link in Obsidian, it triggers a URI request in the format:

- `thoth://doi:10.1234/5678` for DOI-based citations
- `thoth://url:https://example.com/paper.pdf` for URL-based citations

Thoth will download the cited paper, process it, and create a note for it in your Obsidian vault.

### Folder Structure

After running Thoth, your workspace will have the following structure:

```
workspace/
├── data/
│   ├── pdfs/                   # Your research papers in PDF format
│   ├── markdown/               # OCR-generated Markdown files
│   └── notes/                  # Generated Obsidian notes
├── logs/                       # Log files
└── templates/                  # Note templates
```

## Development

1. Install development dependencies:
   ```bash
   uv pip install -e ".[dev]"
   ```

2. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

3. Run tests:
   ```bash
   pytest
   ```

4. Format code:
   ```bash
   black thoth tests
   ```

5. Lint code:
   ```bash
   ruff check thoth tests
   ```

6. Type check:
   ```bash
   mypy thoth
   ```

## Project Structure

```
thoth/
├── main.py                     # Application entry point
├── config.py                   # Configuration module
├── pyproject.toml              # Project metadata and dependencies
├── README.md                   # Documentation
├── .env.example                # Example environment variables
├── data/
│   ├── pdfs/                   # PDF files (monitored)
│   ├── markdown/               # OCR-generated Markdown
│   └── notes/                  # Generated Obsidian notes
├── templates/
│   ├── note_template.md        # Obsidian note template
│   └── prompts/                # LLM prompt templates
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Test fixtures and configuration
│   ├── test_core/              # Tests for core functionality
│   ├── test_citation/          # Tests for citation handling
│   ├── test_linking/           # Tests for link management
│   └── test_uri/               # Tests for URI handling
└── thoth/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── pdf_monitor.py      # Monitors PDF folder
    │   ├── ocr_manager.py      # Handles OCR conversion
    │   ├── markdown_processor.py # Processes Markdown
    │   ├── llm_processor.py    # Processes content with LLM
    │   └── note_generator.py   # Generates notes
    ├── citation/
    │   ├── __init__.py
    │   ├── citation.py         # Citation data model
    │   ├── extractor.py        # Extracts citations
    │   ├── formatter.py        # Formats citations
    │   └── downloader.py       # Downloads cited PDFs
    ├── linking/
    │   ├── __init__.py
    │   ├── manager.py          # Manages relationships
    │   └── updater.py          # Updates existing notes
    ├── uri/
    │   ├── __init__.py
    │   ├── handler.py          # Handles custom URIs
    │   └── generator.py        # Generates URIs
    └── utils/
        ├── __init__.py
        ├── logging.py          # Logging setup
        ├── file.py             # File utilities
        └── text.py             # Text utilities
```

## Troubleshooting

### Common Issues

1. **API Key Errors**:
   - Ensure your Mistral and OpenRouter API keys are correctly set in the `.env` file
   - Check the log file for specific error messages

2. **PDF Processing Failures**:
   - Make sure the PDF is not password-protected
   - Check if the PDF is text-based or scanned (OCR works better with text-based PDFs)

3. **URI Handling Issues**:
   - Verify that your system is configured to handle the `thoth://` URI scheme
   - Check if Thoth is running when you click on a citation link

### Logs

Check the log file specified in your `.env` file for detailed information about any issues:

```bash
tail -f /path/to/your/workspace/logs/thoth.log
```

## License

MIT
