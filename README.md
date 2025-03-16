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

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

4. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

5. Edit the `.env` file with your configuration and API keys.

## Usage

Run Thoth:
```bash
python -m thoth
```

## Development

1. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

2. Run tests:
   ```bash
   pytest
   ```

3. Format code:
   ```bash
   black thoth tests
   ```

4. Lint code:
   ```bash
   ruff check thoth tests
   ```

5. Type check:
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

## License

MIT
