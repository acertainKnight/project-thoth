# Scrape Filter Integration Guide

You're absolutely right - no API needed! Here's how to integrate the Research Assistant's scrape filter directly into your scraping pipeline.

## Simple Integration

### 1. Initialize the Filter Once

```python
from thoth.ingestion.scrape_filter import ScrapeFilter
from thoth.utilities.models import ScrapedArticleMetadata
from datetime import datetime

# Initialize once at the start of your scraper
scrape_filter = ScrapeFilter()
```

### 2. Process Each Scraped Article

```python
def process_new_article(scraped_data):
    # Convert your scraped data to the standard format
    metadata = ScrapedArticleMetadata(
        title=scraped_data['title'],
        authors=scraped_data.get('authors', []),
        abstract=scraped_data.get('abstract'),
        doi=scraped_data.get('doi'),
        arxiv_id=scraped_data.get('arxiv_id'),
        pdf_url=scraped_data.get('pdf_url'),
        journal=scraped_data.get('journal'),
        publication_date=scraped_data.get('publication_date'),
        source='your_scraper_name',  # e.g., 'arxiv', 'pubmed', 'ieee'
        scrape_timestamp=datetime.now().isoformat(),
    )

    # Process through the filter
    result = scrape_filter.process_scraped_article(metadata, download_pdf=True)

    if result['decision'] == 'download':
        print(f"✅ Downloaded: {result['pdf_path']}")
        # Continue with your processing pipeline
        # e.g., send to analysis, add to database, etc.
    else:
        print(f"⏭️  Skipped: {metadata.title}")

    return result
```

### 3. Complete Scraper Example

```python
import time
from your_scraper import get_new_articles  # Your actual scraper

# Initialize filter once
scrape_filter = ScrapeFilter()

while True:
    # Get new articles from your scraper
    new_articles = get_new_articles()

    for article_data in new_articles:
        result = process_new_article(article_data)

        # Optional: Log results or update database
        if result['decision'] == 'download':
            # Article was approved and PDF downloaded
            pdf_path = result['pdf_path']
            # Continue with your processing pipeline

    # Wait before next scrape
    time.sleep(300)  # 5 minutes
```

## What Happens When You Send an Article

1. **Evaluation**: The agent evaluates the article's title/abstract against your research queries
2. **Decision**: Returns 'download' or 'skip' based on relevance scores
3. **PDF Download**: If approved, automatically downloads the PDF to `knowledge/agent/pdfs/`
4. **Logging**: Logs the decision with reasoning to `knowledge/agent/filter.log`

## Log Output Example

```
[2023-12-01T15:30:00] DECISION: DOWNLOAD | SCORE: 0.85 | TITLE: Attention Is All You Need | AUTHORS: Vaswani, A., Shazeer, N. | SOURCE: arxiv | QUERIES: natural_language_processing | MATCHES: transformer, attention, NLP | REASONING: Strong match for NLP and transformer topics
```

## Directory Structure Created

```
knowledge/agent/
├── pdfs/                    # Downloaded PDFs
│   ├── Attention_Is_All_You_Need_arxiv_1706.03762.pdf
│   └── BERT_Pre_training_arxiv_1810.04805.pdf
├── filter.log              # Human-readable log
├── filter.json             # Detailed JSON log
└── evaluations/             # Detailed evaluation results
```

## Benefits of Direct Integration

- **Simple**: No HTTP requests, just function calls
- **Fast**: No network overhead
- **Reliable**: No API server to maintain
- **Flexible**: Easy to customize for your specific scraper
- **Integrated**: Logs and files are managed automatically

## Customization Options

```python
# Use specific queries only
result = scrape_filter.process_scraped_article(
    metadata,
    query_names=['machine_learning_general'],  # Only use this query
    download_pdf=True
)

# Skip PDF download (just get evaluation)
result = scrape_filter.process_scraped_article(
    metadata,
    download_pdf=False
)

# Get statistics
stats = scrape_filter.get_statistics()
print(f"Download rate: {stats['download_rate']:.1%}")
```

## Error Handling

```python
try:
    result = scrape_filter.process_scraped_article(metadata)
    if result['error_message']:
        print(f"Warning: {result['error_message']}")
except Exception as e:
    print(f"Filter error: {e}")
    # Continue with next article
```

## Integration with Existing Thoth Pipeline

After the filter downloads a PDF, you can continue with the existing Thoth analysis:

```python
if result['decision'] == 'download' and result['pdf_path']:
    # Use existing Thoth components
    from thoth.analyze.llm_processor import LLMProcessor

    processor = LLMProcessor()
    analysis = processor.analyze_content(result['pdf_path'])

    # Now you have both the filter decision and full analysis
```

This approach is much simpler and more efficient than using an API for local processing!
