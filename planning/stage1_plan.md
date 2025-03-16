# Thoth AI Research Agent – Stage 1 Implementation Plan

## 1. Overview

Stage 1 of Thoth builds the core PDF processing pipeline with Obsidian integration. This initial version will:

1. Monitor a designated folder for new PDF files
2. Process PDFs using OCR to convert them to Markdown
3. Generate structured Obsidian notes from the Markdown content
4. Extract and process citations with custom URIs
5. Create a citation-based linking system between notes

## 1.1. Project Vision and Stage 1 Context

Thoth is an autonomous research assistant that helps researchers manage academic literature by creating an interconnected knowledge base. Stage 1 establishes the essential foundation for future capabilities.

Stage 1 delivers these key capabilities:

- **PDF Processing Pipeline**: Transform research papers into structured knowledge
- **LLM-Enhanced Content Analysis**: Extract meaningful summaries and findings
- **Citation Network**: Build relationships between papers based on citations
- **Obsidian Integration**: Seamless integration with Obsidian for knowledge management
- **URI-Based Discovery**: Discover and process new papers by clicking citations

This foundation addresses critical pain points in academic research while setting the stage for more advanced features in subsequent development phases.

## 2. System Architecture

### 2.1. Core Components

1. **PDF Monitor**: Watches a folder for new PDF files
2. **OCR Manager**: Converts PDFs to Markdown using Mistral OCR
3. **Markdown Processor**: Extracts metadata and cleans content
4. **LLM Processor**: Analyzes content and extracts citations
5. **Note Generator**: Creates Obsidian-compatible notes
6. **Citation Handler**: Processes citations with dynamic wikilinks
7. **Link Manager**: Maintains citation relationships
8. **URI Handler**: Processes custom URIs when clicked

### 2.2. Configuration Management

The project uses Pydantic for configuration management with environment variables:

   ```python
# Base configuration with sensible defaults
class ThothConfig:
       # Base paths
       workspace_dir: Path
       pdf_dir: Path
       markdown_dir: Path
       notes_dir: Path

       # Logging
       log_level: str = "INFO"
       log_file: Path

       # File monitoring
       watch_interval: int = 5  # seconds
       bulk_process_chunk_size: int = 10
   ```

Example .env file:
```env
# Base Configuration
WORKSPACE_DIR=/path/to/workspace
PDF_DIR=${WORKSPACE_DIR}/pdfs
MARKDOWN_DIR=${WORKSPACE_DIR}/markdown
NOTES_DIR=${WORKSPACE_DIR}/notes
LOG_LEVEL=INFO
LOG_FILE=${WORKSPACE_DIR}/logs/thoth.log

# API Keys
API_MISTRAL_KEY=your_mistral_key
API_OPENROUTER_KEY=your_openrouter_key
```

### 2.3. Data Flow

1. **Input**: PDF file in monitored folder or URL list for bulk processing
2. **Processing**: OCR conversion → Markdown processing → LLM analysis → Citation extraction
3. **Output**: Structured Obsidian note with metadata, summary, and citation links
4. **Link Management**: Update existing notes with proper citation links

## 3. Project Structure

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
│   └── prompts/                # LLM prompt templates using Jinja2
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

## 4. Key Classes and Functions

### 4.1. Core Module

```python
# thoth/core/pdf_monitor.py
def monitor_folder(folder_path: Path, callback: Callable[[Path], None]) -> None:
    """Monitor a folder for new PDF files and call the callback when found."""

def process_url_list(url_file: Path, chunk_size: int = 10) -> list[Path]:
    """Process a list of article URLs in chunks and return downloaded PDF paths."""

# thoth/core/ocr_manager.py
def convert_pdf_to_markdown(pdf_path: Path, api_key: str) -> Path:
    """Convert PDF to Markdown using OCR and return the Markdown path."""

# thoth/core/markdown_processor.py
def process_markdown(markdown_path: Path) -> dict:
    """Process Markdown and return structured data with metadata."""

def extract_metadata(content: str) -> dict:
    """Extract paper metadata from Markdown content."""

# thoth/core/llm_processor.py
def analyze_content(content: str, model: str, api_key: str) -> dict:
    """Analyze content with LLM and return structured data."""

def extract_citations(content: str, model: str, api_key: str) -> list[dict]:
    """Extract citations from content using LLM."""

# thoth/core/note_generator.py
def create_note(content: dict, template_path: Path) -> str:
    """Create an Obsidian note from processed content using a template."""
```

### 4.2. Citation Module

```python
# thoth/citation/extractor.py
def extract_citations(content: str, model: str, api_key: str) -> list[Citation]:
    """Extract citations from paper content using LLM."""

# thoth/citation/formatter.py
def format_citation(citation: Citation, style: str = "ieee") -> str:
    """Format a citation according to the specified style."""

# thoth/citation/downloader.py
def download_citation(citation: Citation) -> Path:
    """Download a cited paper and return the path to the PDF."""
```

### 4.3. Linking Module

```python
# thoth/linking/manager.py
def update_citation_links(new_paper: dict, notes_dir: Path) -> None:
    """Update citation links in existing notes for a new paper."""

def find_citations_to_paper(paper: dict, notes_dir: Path) -> list[tuple[Path, list[dict]]]:
    """Find citations to a paper in existing notes."""

# thoth/linking/updater.py
def update_note_citations(note_path: Path, citations: list[dict]) -> bool:
    """Update citations in a note with proper wikilinks."""
```

### 4.4. URI Module

```python
# thoth/uri/handler.py
def process_uri(uri: str) -> bool:
    """Process a custom URI and trigger appropriate actions."""

# thoth/uri/generator.py
def generate_uri(citation: Citation) -> str:
    """Generate a custom URI for a citation."""
```

### 4.5. Prompt Templates

The project uses Jinja2 templates for LLM prompts to ensure consistency and maintainability:

```python
# Example of using Jinja2 templates for LLM prompts
def analyze_content(content: str, model: str, api_key: str) -> dict:
    """Analyze content with LLM using Jinja2 templates."""
    # Load the template
    template = jinja_env.get_template("analyze_content.j2")

    # Render the template with content
    prompt = template.render(content=content)

    # Use the rendered prompt with LLM
    response = call_llm_api(prompt, model, api_key)

    return parse_response(response)
```

## 5. Application Flow

### 5.1. Initialization

```python
# main.py
def main():
    # Load configuration
    config = load_config()

    # Set up logging
    setup_logging(config.log_level, config.log_file)

    # Initialize components
    pdf_monitor = PDFMonitor(config.pdf_dir)
    ocr_manager = OCRManager(config.api_keys.mistral)
    markdown_processor = MarkdownProcessor()
    llm_processor = LLMProcessor(config.api_keys.openrouter)
    note_generator = NoteGenerator(config.templates_dir)
    link_manager = LinkManager(config.notes_dir)

    # Register callback for new PDFs
    pdf_monitor.on_new_pdf(process_pdf)

    # Start monitoring
    pdf_monitor.start()

    logger.info(f"Thoth started. Monitoring {config.pdf_dir} for new PDFs.")

def process_pdf(pdf_path: Path):
    """Process a new PDF file."""
    try:
        # Convert PDF to Markdown
        markdown_path = ocr_manager.convert_pdf_to_markdown(pdf_path)

        # Process Markdown
        content = markdown_processor.process_markdown(markdown_path)

        # Analyze content with LLM
        analysis = llm_processor.analyze_content(content["text"])

        # Extract citations
        citations = llm_processor.extract_citations(content["text"])

        # Create note
        note_path = note_generator.create_note({
            "metadata": content["metadata"],
            "analysis": analysis,
            "citations": citations,
            "source_files": {
                "pdf": pdf_path,
                "markdown": markdown_path
            }
        })

        # Update citation links
        link_manager.update_citation_links({
            "path": note_path,
            "metadata": content["metadata"],
            "citations": citations
        })

        logger.info(f"Successfully processed {pdf_path.name}")

    except Exception as e:
        logger.error(f"Failed to process {pdf_path.name}: {str(e)}")
```

### 5.2. PDF Processing

When a new PDF is detected:

1. Convert PDF to Markdown using OCR
2. Extract metadata and clean content
3. Analyze content and extract citations using LLM
4. Generate Obsidian note with metadata, summary, and citations
5. Update citation links in existing notes

### 5.3. URI Handling

When a citation URI is clicked in Obsidian:

1. Parse URI to extract citation details
2. Download the cited paper
3. Save PDF to monitored folder (triggering processing)

## 6. Data Models

   ```python
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

     @dataclass
     class Citation:
    """Represents a citation extracted from a paper."""
         title: str
         authors: list[str]
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    context: Optional[str] = None

         def to_ieee_format(self) -> str:
        """Format citation in IEEE style."""
        # Basic implementation
        authors = ", ".join(self.authors)
        result = f"{authors}, \"{self.title}\""
             if self.journal:
            result += f", {self.journal}"
        if self.year:
            result += f", {self.year}"
             if self.doi:
            result += f". DOI: {self.doi}"
        return result

@dataclass
class Paper:
    """Represents a processed paper."""
    path: Path
    title: str
    authors: list[str]
    year: Optional[int] = None
    abstract: Optional[str] = None
    citations: list[Citation] = None

    def __post_init__(self):
        if self.citations is None:
            self.citations = []
```

## 7. Error Handling

   ```python
def process_pdf(pdf_path: Path):
    """Process a new PDF file with error handling."""
    try:
        # Convert PDF to Markdown
        markdown_path = ocr_manager.convert_pdf_to_markdown(pdf_path)
        # ... rest of processing
        logger.info(f"Successfully processed {pdf_path.name}")
    except OCRError as e:
        logger.error(f"OCR failed for {pdf_path.name}: {str(e)}")
        # Add to retry queue
    except LLMError as e:
        # Still create basic note without LLM enhancements
        logger.warning(f"LLM processing failed for {pdf_path.name}: {str(e)}")
        note_path = note_generator.create_basic_note(content["metadata"], pdf_path, markdown_path)
    except Exception as e:
        logger.error(f"Failed to process {pdf_path.name}: {str(e)}")
```

## 8. Dependencies

```toml
# pyproject.toml
[project]
name = "thoth"
version = "0.1.0"
description = "Thoth AI Research Agent - PDF processing with Obsidian integration"
requires-python = ">=3.10"
dependencies = [
    "watchdog>=3.0.0",           # For monitoring PDF folder
    "mistralai>=0.0.7",          # For OCR API access
    "openrouter>=0.0.1",         # For LLM API access
    "jinja2>=3.1.2",             # For template rendering
    "pydantic>=2.4.2",           # For data validation
    "loguru>=0.7.0",             # For logging
    "python-dotenv>=1.0.0",      # For environment variables
    "aiohttp>=3.8.5",            # For async HTTP requests
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "black>=23.7.0",
    "ruff>=0.0.284",
    "mypy>=1.5.1",
]
```

## 9. Development Workflow

   ```bash
# Setup
   git clone https://github.com/yourusername/thoth.git
   cd thoth
python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run
python -m thoth

# Development
pytest                  # Run tests
black thoth tests       # Format code
ruff check thoth tests  # Lint code
mypy thoth              # Type check
   ```

## 10. Git Workflow and Commit Points

The development process should follow a structured git workflow with regular commits at logical points. Each commit should represent a complete, testable unit of work.

### 10.1. Initial Setup Commit

**Commit Point 1: Project Structure and Configuration**
```bash
# After setting up the basic project structure
git add .
git commit -m "Initial project setup with configuration and folder structure"
```
- Create project structure
- Set up configuration system
- Add basic documentation
- Configure development environment
- **Tests**: Configuration loading and validation tests

### 10.2. Core Module Development

**Commit Point 2: PDF Monitor Implementation**
```bash
git add thoth/core/pdf_monitor.py tests/test_core/test_pdf_monitor.py
git commit -m "Implement PDF folder monitoring with watchdog"
```
- Implement folder monitoring
- **Tests**: Test file detection and event handling

**Commit Point 3: OCR Manager Implementation**
```bash
git add thoth/core/ocr_manager.py tests/test_core/test_ocr_manager.py
git commit -m "Implement OCR conversion with Mistral API"
```
- Implement PDF to Markdown conversion
- **Tests**: Test OCR conversion with mock API responses

**Commit Point 4: Markdown Processor Implementation**
```bash
git add thoth/core/markdown_processor.py tests/test_core/test_markdown_processor.py
git commit -m "Implement Markdown processing and metadata extraction"
```
- Implement Markdown cleaning and processing
- Implement metadata extraction
- **Tests**: Test metadata extraction and content cleaning

**Commit Point 5: LLM Processor Implementation**
```bash
git add thoth/core/llm_processor.py tests/test_core/test_llm_processor.py
git commit -m "Implement content analysis with LLM"
```
- Implement content analysis
- **Tests**: Test LLM processing with mock responses

**Commit Point 6: Note Generator Implementation**
```bash
git add thoth/core/note_generator.py tests/test_core/test_note_generator.py
git commit -m "Implement Obsidian note generation"
```
- Implement note template rendering
- **Tests**: Test note generation with sample data

### 10.3. Citation Module Development

**Commit Point 7: Citation Extractor Implementation**
```bash
git add thoth/citation/extractor.py tests/test_citation/test_extractor.py
git commit -m "Implement citation extraction with LLM"
```
- Implement citation extraction
- **Tests**: Test citation extraction with sample content

**Commit Point 8: Citation Formatter Implementation**
```bash
git add thoth/citation/formatter.py tests/test_citation/test_formatter.py
git commit -m "Implement citation formatting in IEEE style"
```
- Implement citation formatting
- **Tests**: Test citation formatting with sample citations

**Commit Point 9: Citation Downloader Implementation**
```bash
git add thoth/citation/downloader.py tests/test_citation/test_downloader.py
git commit -m "Implement citation downloading from DOI/URL"
```
- Implement citation downloading
- **Tests**: Test citation downloading with mock responses

### 10.4. Linking Module Development

**Commit Point 10: Link Manager Implementation**
```bash
git add thoth/linking/manager.py tests/test_linking/test_manager.py
git commit -m "Implement citation link management"
```
- Implement citation link management
- **Tests**: Test finding and updating citation links

**Commit Point 11: Note Updater Implementation**
```bash
git add thoth/linking/updater.py tests/test_linking/test_updater.py
git commit -m "Implement note updating with citation links"
```
- Implement note updating
- **Tests**: Test note updating with sample notes

### 10.5. URI Module Development

**Commit Point 12: URI Handler Implementation**
```bash
git add thoth/uri/handler.py tests/test_uri/test_handler.py
git commit -m "Implement custom URI handling"
```
- Implement URI parsing and handling
- **Tests**: Test URI parsing and processing

**Commit Point 13: URI Generator Implementation**
```bash
git add thoth/uri/generator.py tests/test_uri/test_generator.py
git commit -m "Implement URI generation for citations"
```
- Implement URI generation
- **Tests**: Test URI generation with sample citations

### 10.6. Integration and Main Application

**Commit Point 14: Main Application Implementation**
```bash
git add main.py thoth/__init__.py tests/test_integration.py
git commit -m "Implement main application flow and integration"
```
- Implement main application flow
- Connect all components
- **Tests**: Integration tests with mocked components

**Commit Point 15: Error Handling and Resilience**
```bash
git add thoth/utils/errors.py tests/test_utils/test_errors.py
git commit -m "Implement error handling and resilience strategies"
```
- Implement error handling
- Add retry mechanisms
- **Tests**: Test error handling and recovery

### 10.7. Final Testing and Documentation

**Commit Point 16: End-to-End Testing**
```bash
git add tests/test_e2e.py
git commit -m "Add end-to-end tests with sample PDFs"
```
- Implement end-to-end tests
- **Tests**: Test complete workflow with sample PDFs

**Commit Point 17: Documentation and Examples**
```bash
git add README.md docs/ examples/
git commit -m "Add comprehensive documentation and examples"
```
- Update documentation
- Add usage examples
- Add API documentation

## 11. Testing Strategy

### 11.1. Unit Testing

Each module should have comprehensive unit tests that verify its functionality in isolation:

```python
# tests/test_ocr_manager.py
def test_convert_pdf_to_markdown():
    # Given a PDF file
    pdf_path = Path("tests/fixtures/sample.pdf")

    # When converting to Markdown
    markdown_path = convert_pdf_to_markdown(pdf_path, "mock_api_key")

    # Then a Markdown file should be created
    assert markdown_path.exists()
    assert markdown_path.suffix == ".md"

# tests/test_citation_extractor.py
def test_extract_citations():
    # Given paper content
    content = "... as shown by Smith et al. [1] ..."

    # When extracting citations
    citations = extract_citations(content, "mock_model", "mock_api_key")

    # Then citations should be extracted
    assert len(citations) > 0
    assert citations[0].authors[0].endswith("Smith")
```

### 11.2. Integration Testing

Integration tests should verify that components work together correctly:

```python
# tests/test_integration.py
def test_pdf_processing_flow():
    # Given a PDF file
    pdf_path = Path("tests/fixtures/sample.pdf")

    # When processing the PDF
    result = process_pdf(pdf_path)

    # Then a note should be created
    assert result["note_path"].exists()
    assert result["markdown_path"].exists()

    # And the note should contain citations
    with open(result["note_path"], "r") as f:
        content = f.read()
        assert "## Citations" in content
        assert "[[" in content  # Check for wikilinks
```

### 11.3. End-to-End Testing

End-to-end tests should verify the complete workflow:

```python
# tests/test_e2e.py
def test_complete_workflow():
    # Given a running system
    # And a PDF file in the monitored folder
    pdf_path = Path("data/pdfs/test_paper.pdf")
    shutil.copy("tests/fixtures/sample.pdf", pdf_path)

    # When waiting for processing to complete
    time.sleep(10)  # Allow time for processing

    # Then a note should be created
    note_path = Path("data/notes/test_paper.md")
    assert note_path.exists()

    # And the note should contain expected sections
    with open(note_path, "r") as f:
        content = f.read()
        assert "## Summary" in content
        assert "## Citations" in content
```

### 11.4. Test Fixtures

Use pytest fixtures to set up test environments:

```python
# tests/conftest.py
@pytest.fixture
def sample_pdf():
    """Provide a sample PDF for testing."""
    return Path("tests/fixtures/sample.pdf")

@pytest.fixture
def sample_markdown():
    """Provide sample Markdown content for testing."""
    with open("tests/fixtures/sample.md", "r") as f:
        return f.read()

@pytest.fixture
def mock_ocr_api():
    """Mock the OCR API for testing."""
    with patch("thoth.core.ocr_manager.MistralClient") as mock:
        mock.return_value.process_pdf.return_value = "Sample markdown content"
        yield mock

@pytest.fixture
def mock_llm_api():
    """Mock the LLM API for testing."""
    with patch("thoth.core.llm_processor.OpenRouterClient") as mock:
        mock.return_value.analyze_content.return_value = {
            "summary": "Sample summary",
            "tags": ["tag1", "tag2"]
        }
        mock.return_value.extract_citations.return_value = [
            Citation(
                title="Sample Paper",
                authors=["J. Smith"],
                year=2023,
                journal="Sample Journal"
            )
        ]
        yield mock
```

### 11.5. Continuous Integration

Set up GitHub Actions to run tests automatically:

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Run tests
        run: pytest
      - name: Run linting
        run: |
          black --check thoth tests
          ruff check thoth tests
      - name: Run type checking
        run: mypy thoth
```

## 12. Future Extensibility

The Stage 1 architecture is designed with future extensibility in mind:

1. **Repository Adapters**: Add support for academic repositories (arXiv, PubMed, etc.)
2. **Knowledge Graph**: Evolve the citation network into a full knowledge graph
3. **Enhanced Analysis**: Add more sophisticated content analysis capabilities
4. **User Interfaces**: Support additional interfaces beyond Obsidian

Each component is designed with clear interfaces and separation of concerns to facilitate future enhancements without requiring significant refactoring.
