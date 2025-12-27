# ExtractionService Usage Guide

## Overview

The `ExtractionService` class extracts article metadata from web pages using Playwright browser automation. It supports:

- **Configurable extraction rules** (CSS selectors for article fields)
- **Pagination handling** (automatic navigation through result pages)
- **Deduplication** (skip articles already in database by DOI/title)
- **Error handling** (continue extraction even if individual articles fail)
- **Field mapping** to `ScrapedArticleMetadata` Pydantic schema

## Basic Usage

```python
from thoth.discovery.browser import BrowserManager, ExtractionService

# Initialize browser manager
manager = BrowserManager()
await manager.initialize()

# Get browser context
context = await manager.get_browser(headless=True)
page = await context.new_page()

# Navigate to search results
await page.goto("https://example.com/articles/search?q=machine+learning")

# Configure extraction rules
extraction_rules = {
    "wait_for": ".article-list",  # Wait for this element before extraction
    "article_container": ".article-item",  # Each article's container
    "selectors": {
        "title": "h3.article-title",
        "authors": ".author-name",  # Multiple elements
        "abstract": ".article-abstract",
        "doi": ".article-doi",
        "url": "a.article-link",  # Extracts href attribute
        "pdf_url": "a.pdf-download",
        "publication_date": ".pub-date",
        "journal": ".journal-name",
        "keywords": ".keyword"  # Multiple elements
    },
    "pagination": {
        "type": "button",  # or "link"
        "selector": "button.next-page"
    }
}

# Create extraction service
service = ExtractionService(
    page=page,
    source_name="arxiv_browser",
    existing_dois={"10.1234/example"},  # Optional: skip these DOIs
    existing_titles={"machine learning basics"}  # Optional: skip these titles
)

# Extract articles
articles = await service.extract_articles(
    extraction_rules=extraction_rules,
    max_articles=100
)

# Check statistics
stats = service.extraction_stats
print(f"Extracted: {stats['extracted']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")

# Clean up
await manager.cleanup(context)
await manager.shutdown()
```

## Extraction Rules Configuration

### Required Fields

- **`article_container`**: CSS selector for each article element
- **`selectors`**: Dictionary mapping field names to CSS selectors

### Optional Fields

- **`wait_for`**: Selector to wait for before starting extraction (default: `"body"`)
- **`pagination`**: Configuration for navigating to next pages

### Pagination Configuration

```python
# Button-based pagination
"pagination": {
    "type": "button",
    "selector": "button.next, a.next"
}

# Link-based pagination
"pagination": {
    "type": "link",
    "selector": "a[rel='next']"
}
```

## Selector Types

### Single Text Element
```python
"title": "h3.article-title"  # Extracts text content
```

### Multiple Text Elements
```python
"authors": ".author-name"  # Extracts text from all matching elements
"keywords": ".keyword"
```

### Attribute Extraction
```python
"url": "a.article-link"  # Automatically extracts href attribute
"pdf_url": "a.download-pdf"
```

## Field Mapping to ScrapedArticleMetadata

| Selector Key | Pydantic Field | Type | Required |
|-------------|----------------|------|----------|
| `title` | `title` | str | Yes |
| `authors` | `authors` | List[str] | No |
| `abstract` | `abstract` | str | No |
| `doi` | `doi` | str | No |
| `arxiv_id` | `arxiv_id` | str | No |
| `url` | `url` | str | No |
| `pdf_url` | `pdf_url` | str | No |
| `publication_date` | `publication_date` | str | No |
| `journal` | `journal` | str | No |
| `keywords` | `keywords` | List[str] | No |

Additional metadata:
- `source`: Set from `source_name` parameter
- `scrape_timestamp`: Automatically set to current UTC time

## Deduplication

The service supports two levels of deduplication:

### 1. Pre-existing Articles (Database)
```python
# Get existing articles from database
existing_dois = await article_repo.get_all_dois()
existing_titles = await article_repo.get_all_normalized_titles()

service = ExtractionService(
    page=page,
    existing_dois=existing_dois,
    existing_titles=existing_titles
)
```

### 2. Within Extraction Session
Articles extracted in the same session are automatically deduplicated using:
- DOI (if present)
- Normalized title (lowercase, no punctuation)

## Error Handling

The service handles errors gracefully:

```python
try:
    articles = await service.extract_articles(extraction_rules, max_articles=100)
except ExtractionServiceError as e:
    logger.error(f"Critical extraction error: {e}")
    # Handle critical failure

# Check individual article failures
stats = service.extraction_stats
if stats['errors'] > 0:
    logger.warning(f"{stats['errors']} articles failed to extract")
```

Individual article extraction errors are logged but don't stop the overall process.

## Complete Workflow Example

```python
from thoth.discovery.browser import BrowserManager, ExtractionService
from thoth.repositories.article_repository import ArticleRepository

async def extract_articles_from_browser(url: str, rules: dict, max_articles: int = 100):
    """
    Complete workflow: extract articles from browser-based source.
    """
    manager = BrowserManager()

    try:
        # Initialize browser
        await manager.initialize()
        context = await manager.get_browser()
        page = await context.new_page()

        # Navigate to source
        await page.goto(url)

        # Optional: Perform authentication
        # await page.click("#login-button")
        # await page.fill("#username", "user@example.com")
        # await page.fill("#password", "password")
        # await page.click("#submit")

        # Get existing articles for deduplication
        article_repo = ArticleRepository(postgres_service)
        existing_dois = await article_repo.get_all_dois()

        # Extract articles
        service = ExtractionService(
            page=page,
            source_name="custom_source",
            existing_dois=existing_dois
        )

        articles = await service.extract_articles(
            extraction_rules=rules,
            max_articles=max_articles
        )

        # Log statistics
        stats = service.extraction_stats
        logger.info(
            f"Extraction complete: {stats['extracted']} extracted, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        return articles

    finally:
        # Clean up
        await manager.cleanup(context)
        await manager.shutdown()
```

## Advanced Features

### Relative URL Resolution
URLs are automatically converted to absolute URLs:
```python
# If page URL is: https://example.com/search
# Relative URL: /article/123 → https://example.com/article/123
```

### DOI Cleaning
DOIs are automatically cleaned:
```python
# Input: "DOI: 10.1234/example"
# Output: "10.1234/example"

# Input: "https://doi.org/10.1234/example"
# Output: "10.1234/example"
```

### Title Normalization
Titles are normalized for deduplication:
```python
# "Machine Learning: A Survey" → "machine learning a survey"
```

## Performance Tips

1. **Use headless mode** for production (faster, less resource-intensive)
2. **Set appropriate timeouts** in BrowserManager configuration
3. **Limit max_articles** to prevent long-running extractions
4. **Pre-load existing articles** for efficient deduplication
5. **Use session persistence** for authenticated sources (BrowserManager.save_session)

## Troubleshooting

### No articles extracted
- Check `wait_for` selector is correct
- Verify `article_container` selector matches page structure
- Inspect page using browser DevTools to confirm selectors

### Missing fields
- Check individual field selectors are correct
- Use browser DevTools to verify element structure
- Some fields are optional (only `title` is required)

### Pagination not working
- Verify pagination selector is correct
- Check if "Next" button is disabled on last page
- Test pagination config type ("button" vs "link")

### High error count
- Check browser console for JavaScript errors
- Verify selectors work on all article elements
- Consider increasing timeouts for slow-loading pages
