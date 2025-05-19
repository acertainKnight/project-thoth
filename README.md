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
