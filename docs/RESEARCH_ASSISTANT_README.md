# Research Assistant Agent

The Research Assistant Agent is a conversational AI system that helps you create, refine, and manage research queries for automatic article filtering. It uses LangChain and LangGraph to provide an intelligent interface for building structured queries that determine which research articles should be collected and stored.

## Overview

The Research Assistant Agent serves as an intelligent filter for research articles. Instead of manually reviewing every article, you can:

1. **Create Research Queries**: Define what kinds of articles you're interested in
2. **Refine Queries**: Improve queries based on article evaluation results
3. **Evaluate Articles**: Test how well articles match your research interests
4. **Automatic Filtering**: Let the system automatically filter new articles

## Key Features

### 🤖 Conversational Interface
- Natural language interaction for creating and managing queries
- Context-aware responses that remember your conversation
- Helpful guidance through the query creation process

### 📋 Research Query Management
- Create structured queries with specific criteria
- Edit and refine existing queries
- Delete queries that are no longer needed
- List all available queries

### 🔍 Article Evaluation
- Evaluate articles against research query criteria
- Detailed scoring and reasoning for each evaluation
- Support for multiple queries per article
- Confidence scoring for evaluation results

### 🗂️ Automatic Article Storage
- Automatically categorize articles as approved/rejected/review
- Store articles in organized directory structure
- Maintain evaluation metadata for each article
- Generate statistics on filtering performance

## Architecture

The system consists of several key components:

### Core Components

1. **ResearchAssistantAgent** (`src/thoth/ingestion/agent.py`)
   - Main conversational agent using LangGraph
   - Handles query creation, editing, and evaluation
   - Provides natural language interface

2. **ArticleFilter** (`src/thoth/ingestion/filter.py`)
   - Automatic article filtering based on queries
   - Article storage and organization
   - Evaluation result tracking

3. **Research Models** (`src/thoth/utilities/models.py`)
   - `ResearchQuery`: Structured query definition
   - `QueryEvaluationResponse`: Article evaluation results
   - `ResearchAgentState`: Conversation state management

### Prompt Templates

Located in `templates/prompts/google/`:

- `research_agent_chat.j2`: Main conversational interface
- `evaluate_article_query.j2`: Article evaluation against queries
- `refine_research_query.j2`: Query refinement suggestions

## Research Query Structure

A research query consists of:

```python
ResearchQuery(
    name="unique_query_name",
    description="Human-readable description",
    research_question="Main research question or interest",
    keywords=["keyword1", "keyword2"],           # Important terms
    required_topics=["topic1", "topic2"],       # Must-have topics
    preferred_topics=["topic3", "topic4"],      # Nice-to-have topics
    excluded_topics=["topic5", "topic6"],       # Disqualifying topics
    methodology_preferences=["method1"],         # Preferred methods
    minimum_relevance_score=0.7,                # Threshold (0.0-1.0)
)
```

## Directory Structure

The system creates and manages the following directories:

```
planning/queries/           # Research query JSON files
knowledge/agent/           # Filtered articles storage
├── approved/             # Articles that meet criteria
├── rejected/             # Articles that don't meet criteria
├── review/               # Articles needing manual review
└── evaluations/          # Detailed evaluation results
```

## Usage

### Interactive CLI

Start the conversational interface:

```bash
python -m thoth.ingestion.cli
```

Example interactions:
- "Create a new query for machine learning papers"
- "List my current queries"
- "Help me refine my deep learning query"
- "Evaluate this article against my NLP query"

### Programmatic Usage

```python
from thoth.ingestion.agent import ResearchAssistantAgent
from thoth.ingestion.filter import ArticleFilter
from thoth.utilities.models import ResearchQuery

# Initialize the agent
agent = ResearchAssistantAgent()

# Create a research query
query = ResearchQuery(
    name="ml_healthcare",
    description="Machine learning applications in healthcare",
    research_question="How is ML being applied to healthcare problems?",
    keywords=["machine learning", "healthcare", "medical"],
    required_topics=["machine learning", "healthcare"],
    minimum_relevance_score=0.7
)

# Save the query
agent.create_query(query)

# Evaluate an article
evaluation = agent.evaluate_article(article_analysis, "ml_healthcare")
print(f"Score: {evaluation.relevance_score}")
print(f"Recommendation: {evaluation.recommendation}")

# Set up automatic filtering
article_filter = ArticleFilter(agent)
result = article_filter.filter_article(article_analysis, article_path)
```

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
