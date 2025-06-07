# Thoth Discovery System

The Thoth Discovery System is a comprehensive article discovery and scraping framework that extends the existing Thoth AI research assistant with automated article discovery capabilities. It provides both API-based search tools and flexible web scraping with a point-and-click Chrome extension for configuration.

## Features

### 🔍 **Multi-Source Discovery**
- **API Sources**: ArXiv and PubMed integration with configurable search parameters
- **Web Scraping**: Flexible scraper that works with any website using CSS selectors
- **Chrome Extension**: Point-and-click interface for configuring scrapers without coding

### ⏰ **Intelligent Scheduling**
- **Configurable Cadences**: Set different intervals for each source (hourly, daily, weekly)
- **Time Preferences**: Schedule runs at specific times of day
- **Day-of-Week Filtering**: Run only on specific days (e.g., weekdays only)
- **Rate Limiting**: Built-in rate limiting to respect website policies

### 🎯 **Smart Filtering Integration**
- **Research Query Matching**: Integrates with existing research query system
- **Automatic PDF Download**: Downloads PDFs for articles that pass filtering
- **Relevance Scoring**: Uses LLM-based evaluation to score article relevance
- **Batch Processing**: Efficiently processes multiple articles with configurable limits

### 📊 **Monitoring & Analytics**
- **Discovery Results Tracking**: Detailed logs of all discovery runs
- **Statistics Dashboard**: View discovery performance over time
- **Error Reporting**: Comprehensive error tracking and reporting
- **Source Performance**: Monitor individual source effectiveness

## Quick Start

### 1. Basic Setup

The discovery system is automatically available when you install Thoth. No additional setup is required for basic functionality.

### 2. Create Your First Discovery Source

#### ArXiv Source Example
```bash
# Create an ArXiv source for machine learning papers
python -m thoth discovery create \
  --name "arxiv_ml" \
  --type "api" \
  --description "ArXiv machine learning papers" \
  --config-file arxiv_ml_config.json
```

Create `arxiv_ml_config.json`:
```json
{
  "api_config": {
    "source": "arxiv",
    "categories": ["cs.LG", "cs.AI", "cs.CL"],
    "keywords": ["machine learning", "neural networks", "transformer"],
    "sort_by": "lastUpdatedDate",
    "sort_order": "descending"
  },
  "schedule_config": {
    "interval_minutes": 360,
    "max_articles_per_run": 25,
    "enabled": true,
    "time_of_day": "09:00",
    "days_of_week": [0, 1, 2, 3, 4]
  },
  "query_filters": ["machine_learning", "nlp_research"]
}
```

#### Web Scraping Source Example
```bash
# Create a web scraping source
python -m thoth discovery create \
  --name "nature_ai" \
  --type "scraper" \
  --description "Nature AI articles" \
  --config-file nature_scraper_config.json
```

Create `nature_scraper_config.json`:
```json
{
  "scraper_config": {
    "base_url": "https://www.nature.com/subjects/machine-learning",
    "extraction_rules": {
      "title": {
        "selector": "h3.c-card__title a",
        "attribute": "text"
      },
      "authors": {
        "selector": ".c-author-list .c-author-list__item",
        "attribute": "text",
        "multiple": true
      },
      "abstract": {
        "selector": ".c-card__summary",
        "attribute": "text"
      },
      "url": {
        "selector": "h3.c-card__title a",
        "attribute": "href"
      },
      "publication_date": {
        "selector": ".c-meta__item time",
        "attribute": "datetime"
      }
    },
    "pagination_config": {
      "enabled": true,
      "type": "link",
      "next_selector": "a[rel='next']",
      "max_pages": 3
    },
    "rate_limiting": {
      "delay": 2.0
    }
  }
}
```

### 3. Run Discovery

```bash
# Run discovery for all active sources
python -m thoth discovery run

# Run discovery for a specific source
python -m thoth discovery run --source arxiv_ml --max-articles 10

# List all configured sources
python -m thoth discovery list
```

### 4. Start the Scheduler

```bash
# Start the discovery scheduler (runs in background)
python -m thoth discovery scheduler start

# Check scheduler status
python -m thoth discovery scheduler status
```

## Chrome Extension Setup

### 1. Install the Extension

The Chrome extension allows you to configure web scrapers through a point-and-click interface directly in your browser.

1. Start the Chrome extension server:
```bash
python -m thoth.discovery.chrome_extension
```

2. Install the Chrome extension (extension files would be provided separately)

3. Navigate to any website you want to scrape

4. Click the Thoth extension icon and start configuring selectors

### 2. Using the Extension

1. **Select Elements**: Click on page elements to automatically generate CSS selectors
2. **Test Selectors**: Real-time testing shows what data would be extracted
3. **Configure Fields**: Map page elements to article fields (title, authors, abstract, etc.)
4. **Save Configuration**: Save your scraper configuration for reuse
5. **Test Scraping**: Run a full test to see extracted articles

### Web Emulator Recording

For sites that require manual navigation or login, you can launch a browser
emulator and record your actions:

```bash
python -m thoth.discovery.web_emulator <url>
```

The recorder will open a Chrome window where you can log in and navigate to the
desired page. When you close the window a ``BrowserRecording`` file is saved
with the final URL and your session cookies. This recording can be combined with
a scrape configuration to create an ``emulator`` discovery source.

## API Sources Configuration

### ArXiv Configuration Options

```json
{
  "api_config": {
    "source": "arxiv",
    "categories": ["cs.LG", "cs.AI", "cs.CL", "cs.CV"],
    "keywords": ["transformer", "attention", "BERT"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "sort_by": "lastUpdatedDate",
    "sort_order": "descending"
  }
}
```

**Available Categories**: cs.AI, cs.CL, cs.CV, cs.LG, cs.NE, stat.ML, and more

### PubMed Configuration Options

```json
{
  "api_config": {
    "source": "pubmed",
    "keywords": ["machine learning", "artificial intelligence"],
    "mesh_terms": ["Artificial Intelligence", "Machine Learning"],
    "authors": ["Smith J", "Doe A"],
    "journal": "Nature",
    "start_date": "2023/01/01",
    "end_date": "2023/12/31",
    "publication_types": ["Journal Article", "Review"]
  }
}
```

## Web Scraping Configuration

### Extraction Rules

Define how to extract data from web pages using CSS selectors:

```json
{
  "extraction_rules": {
    "title": {
      "selector": "h1.article-title",
      "attribute": "text"
    },
    "authors": {
      "selector": ".author-list .author",
      "attribute": "text",
      "multiple": true
    },
    "abstract": {
      "selector": ".abstract p",
      "attribute": "text"
    },
    "pdf_url": {
      "selector": "a.pdf-link",
      "attribute": "href"
    },
    "doi": {
      "selector": "[data-doi]",
      "attribute": "data-doi"
    }
  }
}
```

### Navigation Rules

Configure how to navigate through pages:

```json
{
  "navigation_rules": {
    "article_container": ".article-item",
    "click_selectors": [".load-more-button"],
    "wait_time": 2
  }
}
```

### Pagination Configuration

Handle multi-page results:

```json
{
  "pagination_config": {
    "enabled": true,
    "type": "link",
    "next_selector": "a.next-page",
    "max_pages": 5
  }
}
```

Or for parameter-based pagination:

```json
{
  "pagination_config": {
    "enabled": true,
    "type": "parameter",
    "page_parameter": "page",
    "max_pages": 10
  }
}
```

## Scheduling Configuration

### Basic Scheduling

```json
{
  "schedule_config": {
    "interval_minutes": 60,
    "max_articles_per_run": 50,
    "enabled": true
  }
}
```

### Advanced Scheduling

```json
{
  "schedule_config": {
    "interval_minutes": 240,
    "max_articles_per_run": 25,
    "enabled": true,
    "time_of_day": "09:00",
    "days_of_week": [0, 1, 2, 3, 4]
  }
}
```

**Days of Week**: 0=Monday, 1=Tuesday, ..., 6=Sunday

## Integration with Research Queries

The discovery system integrates seamlessly with Thoth's existing research query system:

### 1. Create Research Queries

```bash
# Use the existing research agent to create queries
python -m thoth.ingestion.cli
```

### 2. Link Sources to Queries

When creating discovery sources, specify which research queries should be used for filtering:

```json
{
  "query_filters": ["machine_learning", "nlp_research", "computer_vision"]
}
```

### 3. Automatic Filtering

Discovered articles are automatically:
1. Evaluated against specified research queries
2. Scored for relevance using LLM analysis
3. Downloaded as PDFs if they pass filtering criteria
4. Processed through the full Thoth pipeline

## Command Line Interface

### Discovery Commands

```bash
# Run discovery
python -m thoth discovery run [--source SOURCE] [--max-articles N]

# List sources
python -m thoth discovery list

# Create source
python -m thoth discovery create --name NAME --type TYPE --description DESC [--config-file FILE]

# Scheduler commands
python -m thoth discovery scheduler start
python -m thoth discovery scheduler stop
python -m thoth discovery scheduler status
```

### Testing Commands

```bash
# Test scrape filter
python -m thoth scrape-filter [--create-sample-queries]
```

## Configuration Files

### Environment Variables

Add to your `.env` file:

```bash
# Discovery system settings
DISCOVERY_AUTO_START_SCHEDULER=false
DISCOVERY_DEFAULT_MAX_ARTICLES=50
DISCOVERY_DEFAULT_INTERVAL_MINUTES=60
DISCOVERY_RATE_LIMIT_DELAY=1.0
DISCOVERY_CHROME_EXTENSION_ENABLED=true
DISCOVERY_CHROME_EXTENSION_PORT=8765
```

### Directory Structure

The discovery system creates the following directories:

```
data/
├── discovery/
│   ├── sources/          # Discovery source configurations
│   ├── results/          # Discovery run results and logs
│   └── chrome_configs/   # Chrome extension configurations
├── agent/
│   ├── discovery_sources/    # Source configurations (alternative location)
│   ├── discovery_results/    # Results storage
│   └── discovery_schedule.json  # Scheduler state
```

## Monitoring and Analytics

### View Discovery Statistics

```python
from thoth.discovery import DiscoveryManager

manager = DiscoveryManager()
stats = manager.get_discovery_statistics(days=7)

print(f"Total articles found: {stats['total_articles_found']}")
print(f"Total articles downloaded: {stats['total_articles_downloaded']}")
print(f"Average execution time: {stats['average_execution_time']:.2f}s")
```

### Scheduler Status

```python
from thoth.discovery import DiscoveryScheduler

scheduler = DiscoveryScheduler()
status = scheduler.get_schedule_status()

print(f"Scheduler running: {status['running']}")
print(f"Active sources: {status['enabled_sources']}")

# View upcoming runs
upcoming = scheduler.get_next_scheduled_runs(hours=24)
for run in upcoming:
    print(f"{run['source_name']}: {run['scheduled_time']}")
```

## Best Practices

### 1. Rate Limiting
- Always configure appropriate delays between requests
- Respect robots.txt and website terms of service
- Start with longer delays and optimize based on website response

### 2. Selector Robustness
- Use specific but not overly fragile CSS selectors
- Test selectors on multiple pages
- Include fallback selectors when possible

### 3. Error Handling
- Monitor discovery logs regularly
- Set up alerts for repeated failures
- Test configurations before deploying to production

### 4. Resource Management
- Limit max_articles_per_run to avoid overwhelming the system
- Schedule discovery during off-peak hours
- Monitor disk space for downloaded PDFs

### 5. Query Optimization
- Create specific research queries for better filtering
- Regularly review and update query criteria
- Use exclusion topics to filter out irrelevant content

## Troubleshooting

### Common Issues

1. **Selectors Not Working**
   - Website structure may have changed
   - Use browser developer tools to verify selectors
   - Test with the Chrome extension

2. **Rate Limiting Errors**
   - Increase delay in rate_limiting configuration
   - Check if website has specific rate limits
   - Consider using proxy rotation for high-volume scraping

3. **PDF Download Failures**
   - Verify PDF URLs are accessible
   - Check if authentication is required
   - Ensure sufficient disk space

4. **Scheduler Not Running**
   - Check if scheduler process is active
   - Verify schedule configuration syntax
   - Review scheduler logs for errors

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('thoth.discovery').setLevel(logging.DEBUG)
```

### Testing Configurations

Always test new configurations:

```python
from thoth.discovery import WebScraper
from thoth.utilities.models import ScrapeConfiguration

scraper = WebScraper()
config = ScrapeConfiguration(...)
result = scraper.test_configuration(config)

print(f"Success: {result['success']}")
print(f"Articles found: {result['articles_found']}")
print(f"Errors: {result['errors']}")
```

## Advanced Usage

### Custom API Sources

Extend the system with custom API sources:

```python
from thoth.discovery.api_sources import BaseAPISource
from thoth.utilities.models import ScrapedArticleMetadata

class CustomAPISource(BaseAPISource):
    def search(self, config, max_results=50):
        # Implement your custom API logic
        articles = []
        # ... fetch and parse articles ...
        return articles
```

### Custom Transformations

Add custom data transformations:

```json
{
  "extraction_rules": {
    "title": {
      "selector": "h1",
      "attribute": "text",
      "transform": {
        "type": "regex",
        "pattern": "^Title: ",
        "replacement": ""
      }
    }
  }
}
```

### Webhook Integration

Set up webhooks for discovery events:

```python
from thoth.discovery import DiscoveryManager

def on_discovery_complete(result):
    # Send notification, update database, etc.
    pass

manager = DiscoveryManager()
manager.add_webhook('discovery_complete', on_discovery_complete)
```

## Contributing

The discovery system is designed to be extensible. Contributions are welcome for:

- New API source integrations
- Enhanced web scraping capabilities
- Improved Chrome extension features
- Additional scheduling options
- Better error handling and monitoring

## License

The Thoth Discovery System is part of the Thoth project and follows the same licensing terms.
