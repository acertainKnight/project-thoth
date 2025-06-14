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
from thoth.utilities.schemas import ScrapedArticleMetadata
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
from thoth.utilities.schemas import ScrapedArticleMetadata

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

## What Happens When You Send an Article

1. **Evaluation**: The agent evaluates the article's title/abstract against your research queries
- **Simple**: No HTTP requests, just function calls
- **Fast**: No network overhead
- **Reliable**: No API server to maintain

## Customization Options

```python
# Use specific queries only
result = scrape_filter.process_scraped_article(
```

## Error Handling

```python
try:
    result = scrape_filter.process_scraped_article(metadata)
```

## Integration with Existing Thoth Pipeline

After the filter downloads a PDF, you can continue with the existing Thoth analysis:

```python
if result['decision'] == 'download' and result['pdf_path']:
```

This approach is much simpler and more efficient than using an API for local processing!

from thoth.ingestion.filter import ArticleFilter
from thoth.utilities.models import ResearchQuery

# Initialize the agent
agent = ResearchAssistantAgent()

### Integration with Existing Pipeline

The Research Assistant integrates with the existing Thoth pipeline:

```python
from thoth.analyze.llm_processor import LLMProcessor
from thoth.ingestion.filter import ArticleFilter

# Analyze an article
processor = LLMProcessor()
analysis = processor.analyze_content("path/to/article.md")

# Filter based on research queries
article_filter = ArticleFilter()
filter_result = article_filter.filter_article(
    article=analysis,
    article_path=Path("path/to/article.md")
)

if filter_result["overall_recommendation"] == "keep":
    print(f"Article approved! Stored at: {filter_result['stored_path']}")
```

## Configuration

The system uses the existing Thoth configuration system. Add these settings to your `.env` file:

```bash
# Research agent directories
QUERIES_DIR=${WORKSPACE_DIR}/planning/queries
AGENT_STORAGE_DIR=${WORKSPACE_DIR}/knowledge/agent
```

## Example Workflow

1. **Create Research Queries**
   ```bash
   python -m thoth.ingestion.cli
   # "Create a new query for deep learning papers"
   ```

2. **Test with Sample Articles**
   ```bash
   python examples/research_assistant_demo.py
   ```

3. **Integrate with Article Processing**
   ```python
   # In your article processing pipeline
   filter_result = article_filter.filter_article(analysis, article_path)

   if filter_result["overall_recommendation"] == "keep":
       # Process and store the article
       process_approved_article(article_path)
   ```

4. **Review and Refine**
   - Check articles in the "review" category
   - Refine queries based on evaluation results
   - Adjust relevance score thresholds

## Advanced Features

### Query Refinement

The system can suggest improvements to your queries:

```python
# Get refinement suggestions
suggestions = agent.refinement_llm.invoke({
    "query": query.model_dump(),
    "recent_evaluations": evaluation_history,
    "user_feedback": "Too many false positives"
})
```

### Batch Processing

Process multiple articles at once:

```python
for article_path in article_paths:
    analysis = processor.analyze_content(article_path)
    filter_result = article_filter.filter_article(analysis, article_path)
    print(f"{article_path}: {filter_result['overall_recommendation']}")
```

### Statistics and Monitoring

Track filtering performance:

```python
stats = article_filter.get_statistics()
print(f"Approval rate: {stats['approved_count'] / stats['total_articles']:.2%}")
```

## Best Practices

### Creating Effective Queries

1. **Be Specific**: Include specific keywords and topics
2. **Use Exclusions**: Define what you don't want to avoid false positives
3. **Set Appropriate Thresholds**: Start with 0.7 and adjust based on results
4. **Include Methodology Preferences**: Specify preferred research approaches

### Query Management

1. **Start Simple**: Begin with basic queries and refine over time
2. **Test Regularly**: Evaluate sample articles to validate query effectiveness
3. **Monitor Results**: Review articles in the "review" category
4. **Iterate**: Refine queries based on evaluation results

### Integration Tips

1. **Batch Processing**: Process articles in batches for efficiency
2. **Error Handling**: Implement proper error handling for production use
3. **Logging**: Monitor agent performance and evaluation results
4. **Backup**: Regularly backup your query files

## Troubleshooting

### Common Issues

1. **No Queries Available**
   - Create at least one research query before filtering articles
   - Check that query files are properly saved in the queries directory

2. **Low Evaluation Scores**
   - Review and refine query keywords and topics
   - Consider lowering the minimum relevance score threshold
   - Check that articles contain relevant content

3. **Template Not Found Errors**
   - Ensure prompt templates exist in the correct directory
   - Check that the model name in configuration matches the template directory

4. **Permission Errors**
   - Verify write permissions for queries and agent storage directories
   - Check that directories are created with proper permissions

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use loguru configuration
from loguru import logger
logger.add("debug.log", level="DEBUG")
```

## Future Enhancements

Planned improvements include:

1. **Multi-language Support**: Queries and evaluation in multiple languages
2. **Advanced Query Types**: Support for more complex query logic
3. **Machine Learning Integration**: Learn from user feedback to improve queries
4. **Web Interface**: Browser-based interface for query management
5. **Integration with Citation Networks**: Use citation relationships for evaluation
6. **Collaborative Filtering**: Share and discover queries from other researchers

## Contributing

To contribute to the Research Assistant Agent:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for any changes
4. Ensure compatibility with the existing Thoth pipeline

## Support

For questions or issues:

1. Check the troubleshooting section above
2. Review the example scripts in the `examples/` directory
3. Examine the test files for usage patterns
4. Create an issue with detailed error information
