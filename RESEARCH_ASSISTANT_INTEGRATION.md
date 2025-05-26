# Research Assistant Integration with Thoth

The Research Assistant is now fully integrated with your existing Thoth system through `main.py` and `pipeline.py`.

## Configuration

### Environment Variables (`.env`)

The following variables are already configured in your `.env` file:

```bash
# Research agent directories
QUERIES_DIR=${WORKSPACE_DIR}/planning/queries
AGENT_STORAGE_DIR=${WORKSPACE_DIR}/knowledge/agent

# Research agent settings
RESEARCH_AGENT_AUTO_START=false
RESEARCH_AGENT_DEFAULT_QUERIES=true
```

### Configuration Class (`config.py`)

A new `ResearchAgentConfig` class has been added to handle research agent settings:

```python
class ResearchAgentConfig(BaseSettings):
    auto_start: bool = Field(False, description='Whether to automatically start the research agent CLI')
    default_queries: bool = Field(True, description='Whether to create default research queries on first run')
```

## Command Line Usage

### 1. Interactive Research Assistant

Start the conversational interface to create and manage research queries:

```bash
python -m thoth.main research-agent
```

This opens an interactive chat where you can:
- Create new research queries
- List existing queries
- Edit and refine queries
- Test queries against sample articles

### 2. Test Scrape Filter

Test the scrape filtering system with sample data:

```bash
# Test with existing queries
python -m thoth.main scrape-filter

# Create sample queries and test
python -m thoth.main scrape-filter --create-sample-queries
```

This will:
- Create sample research queries (if `--create-sample-queries` is used)
- Test filtering with a sample article
- Show filtering results and statistics
- Display log file locations

## Integration with Pipeline

### Accessing the Scrape Filter

The `ThothPipeline` class now includes a `scrape_filter` property:

```python
from thoth.pipeline import ThothPipeline

pipeline = ThothPipeline()

# Access the scrape filter (lazy-loaded)
scrape_filter = pipeline.scrape_filter

# Use it to filter articles
result = scrape_filter.process_scraped_article(metadata)
```

### Direct Integration in Your Scraper

```python
from thoth.pipeline import ThothPipeline
from thoth.utilities.models import ScrapedArticleMetadata
from datetime import datetime

# Initialize pipeline once
pipeline = ThothPipeline()

# In your scraping loop
def process_scraped_article(scraped_data):
    # Convert to standard format
    metadata = ScrapedArticleMetadata(
        title=scraped_data['title'],
        authors=scraped_data.get('authors', []),
        abstract=scraped_data.get('abstract'),
        pdf_url=scraped_data.get('pdf_url'),
        source='your_scraper_name',
        scrape_timestamp=datetime.now().isoformat(),
    )

    # Filter through research queries
    result = pipeline.scrape_filter.process_scraped_article(metadata)

    if result['decision'] == 'download':
        print(f"✅ Downloaded: {result['pdf_path']}")

        # Continue with existing Thoth pipeline
        if result['pdf_path']:
            note_path = pipeline.process_pdf(result['pdf_path'])
            print(f"📝 Note created: {note_path}")
    else:
        print(f"⏭️  Skipped: {metadata.title}")

    return result
```

## Workflow Examples

### 1. Setting Up Research Queries

```bash
# Start interactive assistant
python -m thoth.main research-agent

# In the chat interface:
# "Create a new query for machine learning papers"
# "I want papers about transformer architectures and attention mechanisms"
# "List my queries"
```

### 2. Testing Your Setup

```bash
# Create sample queries and test
python -m thoth.main scrape-filter --create-sample-queries

# Check the results
ls -la knowledge/agent/
cat knowledge/agent/filter.log
```

### 3. Integrating with Your Scraper

```python
# your_scraper.py
from thoth.pipeline import ThothPipeline
from thoth.utilities.models import ScrapedArticleMetadata

pipeline = ThothPipeline()

while True:
    # Your scraping logic
    new_articles = scrape_new_articles()

    for article_data in new_articles:
        metadata = ScrapedArticleMetadata(
            title=article_data['title'],
            # ... other fields
            source='your_scraper',
        )

        # Filter and potentially download
        result = pipeline.scrape_filter.process_scraped_article(metadata)

        # If approved, continue with full Thoth processing
        if result['decision'] == 'download' and result['pdf_path']:
            note_path = pipeline.process_pdf(result['pdf_path'])
```

## Directory Structure

The system creates and manages:

```
planning/queries/           # Research query JSON files
├── machine_learning_general.json
└── natural_language_processing.json

knowledge/agent/           # Filtered articles and logs
├── pdfs/                 # Downloaded PDFs
├── filter.log           # Human-readable filtering log
├── filter.json          # Detailed JSON log
└── evaluations/         # Detailed evaluation results
```

## Log Output

The system logs all filtering decisions:

```
[2023-12-01T15:30:00] DECISION: DOWNLOAD | SCORE: 0.85 | TITLE: Attention Is All You Need | AUTHORS: Vaswani, A., Shazeer, N. | SOURCE: arxiv | QUERIES: natural_language_processing | MATCHES: transformer, attention | REASONING: Strong match for NLP and transformer topics
```

## Benefits of Integration

1. **Unified Configuration**: Uses your existing `.env` and `config.py` setup
2. **Command Line Interface**: Integrates with your existing `main.py` commands
3. **Pipeline Integration**: Works seamlessly with `ThothPipeline`
4. **Automatic Setup**: Directories and configurations are handled automatically
5. **Consistent Logging**: Uses your existing logging configuration

## Next Steps

1. **Create Research Queries**: Use `python -m thoth.main research-agent` to set up your research interests
2. **Test the System**: Run `python -m thoth.main scrape-filter --create-sample-queries` to verify everything works
3. **Integrate with Scraper**: Add the scrape filter to your existing scraping pipeline
4. **Monitor Results**: Check the logs in `knowledge/agent/filter.log` to see filtering decisions

The Research Assistant is now a fully integrated part of your Thoth system!
