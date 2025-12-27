# Browser Workflow Discovery Plugin

## Overview

The `BrowserWorkflowPlugin` integrates browser automation workflows as a discovery source, enabling article discovery from websites that require authentication, form submissions, or JavaScript rendering.

## Features

- **Inherits from BaseDiscoveryPlugin**: Follows standard plugin architecture
- **Source type registration**: "browser_workflow"
- **Async execution**: Handles browser automation asynchronously
- **Query parameter support**: keywords, date_range, custom_filters
- **Error handling**: Continues on failures, logs errors comprehensively
- **Service integration**: Works with WorkflowExecutionService
- **Statistics tracking**: Links executions to query_id, updates workflow stats

## Architecture

```
BrowserWorkflowPlugin
├── PostgresService (database access)
└── WorkflowExecutionService
    ├── BrowserManager (browser lifecycle)
    ├── WorkflowEngine (workflow execution)
    ├── ExtractionService (article extraction)
    └── Repositories (workflow, search config, executions)
```

## Installation

The plugin is automatically registered when importing from the plugins module:

```python
from thoth.discovery.plugins import plugin_registry

# Plugin is registered as 'browser_workflow'
plugin = plugin_registry.create(
    'browser_workflow',
    postgres_service=postgres,
    config={'workflow_id': 'uuid-string'}
)
```

## Configuration

### Required Config

- `workflow_id` (str): UUID of the browser workflow to execute

### Optional Config

- `max_articles` (int): Maximum articles to extract (default: 100)
- `max_concurrent_browsers` (int): Concurrent browser instances (default: 5)
- `timeout` (int): Execution timeout in milliseconds (default: 30000)
- `max_retries` (int): Maximum retry attempts (default: 3)

### Example Configuration

```python
config = {
    'workflow_id': '123e4567-e89b-12d3-a456-426614174000',
    'max_articles': 50,
    'max_concurrent_browsers': 3,
    'timeout': 45000,
    'max_retries': 2,
}
```

## Usage

### Basic Usage

```python
from uuid import UUID
from thoth.discovery.plugins import BrowserWorkflowPlugin
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas import ResearchQuery

# Initialize
postgres = PostgresService()
await postgres.initialize()

plugin = BrowserWorkflowPlugin(
    postgres_service=postgres,
    config={'workflow_id': 'your-workflow-uuid'}
)
await plugin.initialize()

# Create query
query = ResearchQuery(
    name='ML Research',
    research_question='Latest advances in ML?',
    keywords=['machine learning', 'neural networks']
)

# Discover articles
articles = await plugin.discover_async(
    query=query,
    max_results=50,
    query_id=UUID('query-uuid')  # Optional
)

# Cleanup
await plugin.shutdown()
```

### Query Parameter Mapping

The plugin maps `ResearchQuery` fields to `ExecutionParameters`:

| ResearchQuery Field | ExecutionParameters Field | Description |
|---------------------|--------------------------|-------------|
| `keywords` | `keywords` | Combined with required_topics |
| `required_topics` | `keywords` | Merged into keywords list |
| `publication_date_range` | `date_range` | Converted to string format |
| `preferred_topics` | `custom_filters['preferred_topics']` | Preference filters |
| `excluded_topics` | `custom_filters['excluded_topics']` | Exclusion filters |
| `methodology_preferences` | `custom_filters['methodology']` | Methodology filters |
| `research_question` | `custom_filters['research_question']` | Context for search |

### Error Handling

The plugin handles errors gracefully:

1. **Initialization errors**: Raise `BrowserWorkflowPluginError`
2. **Execution errors**: Log error, return empty list
3. **Service errors**: Catch and log, continue discovery
4. **Unexpected errors**: Log with stack trace, return empty list

This ensures other discovery sources can continue if workflow fails.

## Integration with Discovery System

### Plugin Registry

```python
from thoth.discovery.plugins import plugin_registry

# List all plugins
plugins = plugin_registry.list_plugins()
# ['arxiv', 'browser_workflow', ...]

# Create plugin instance
plugin = plugin_registry.create(
    'browser_workflow',
    postgres_service=postgres,
    config={'workflow_id': 'uuid'}
)
```

### Discovery Service Integration

```python
from thoth.services.discovery_service import DiscoveryService

# Discovery service can use browser workflow as a source
discovery = DiscoveryService(postgres)

# Add browser workflow source
await discovery.add_source(
    source_type='browser_workflow',
    config={'workflow_id': 'workflow-uuid'},
    query_id=query_id
)

# Execute discovery across all sources
results = await discovery.discover_all(query)
```

## Workflow Execution Flow

1. **Validation**:
   - Check plugin initialized
   - Validate workflow_id in config
   - Convert workflow_id string to UUID

2. **Parameter Building**:
   - Extract keywords from query
   - Convert date ranges
   - Build custom filters

3. **Execution**:
   - Call WorkflowExecutionService.execute_workflow()
   - Pass ExecutionParameters
   - Link to query_id if provided

4. **Result Processing**:
   - Extract articles from WorkflowExecutionOutput
   - Log execution statistics
   - Return ScrapedArticleMetadata list

5. **Error Handling**:
   - Log errors comprehensively
   - Return empty list on failure
   - Don't block other discovery sources

## Statistics and Monitoring

The plugin tracks execution statistics:

- **execution_id**: UUID of workflow execution
- **success**: Whether execution succeeded
- **articles_count**: Number of articles found
- **duration_ms**: Execution duration in milliseconds
- **pages_visited**: Number of pages browser visited
- **error_message**: Error details if failed

These statistics are stored in the database and can be queried:

```python
# Get workflow execution history
executions = await plugin.execution_service.executions_repo.get_by_workflow_id(
    workflow_id=workflow_id
)

# Get execution statistics
for execution in executions:
    print(f"Execution {execution['execution_id']}:")
    print(f"  Success: {execution['success']}")
    print(f"  Articles: {execution['articles_extracted']}")
    print(f"  Duration: {execution['duration_ms']}ms")
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

@pytest.mark.asyncio
async def test_browser_workflow_plugin_discovery():
    """Test basic workflow execution."""
    # Setup
    postgres = Mock(spec=PostgresService)
    workflow_id = uuid4()

    plugin = BrowserWorkflowPlugin(
        postgres_service=postgres,
        config={'workflow_id': str(workflow_id)}
    )

    # Mock execution service
    plugin.execution_service.execute_workflow = AsyncMock(
        return_value=Mock(
            articles=[],
            stats=Mock(success=True, articles_count=0)
        )
    )

    await plugin.initialize()

    # Test
    query = ResearchQuery(
        name='Test',
        research_question='Test question',
        keywords=['test']
    )

    articles = await plugin.discover_async(query, max_results=10)

    # Verify
    assert isinstance(articles, list)
    plugin.execution_service.execute_workflow.assert_called_once()
```

## Performance Considerations

- **Browser overhead**: Each workflow spawns browser instance(s)
- **Execution time**: Typically 5-60 seconds depending on workflow complexity
- **Concurrency**: Limited by `max_concurrent_browsers` setting
- **Memory**: Browser instances can use 200-500MB each
- **Network**: Depends on target website and number of pages visited

### Optimization Tips

1. **Limit concurrent browsers**: Set reasonable `max_concurrent_browsers` (3-5)
2. **Set appropriate timeouts**: Balance thoroughness vs. speed
3. **Use targeted workflows**: Specific searches execute faster
4. **Cache results**: Consider caching at discovery service level
5. **Monitor resources**: Track browser memory and CPU usage

## Troubleshooting

### Plugin Not Initialized

```
BrowserWorkflowPluginError: Plugin not initialized. Call initialize() first.
```

**Solution**: Call `await plugin.initialize()` before `discover_async()`

### Invalid Workflow ID

```
BrowserWorkflowPluginError: Invalid workflow_id format: invalid-uuid
```

**Solution**: Ensure `workflow_id` in config is valid UUID string

### Workflow Not Found

```
WorkflowExecutionServiceError: Workflow not found: <uuid>
```

**Solution**: Verify workflow exists in database and is active

### Browser Timeout

```
Workflow execution failed: Browser timeout after 30000ms
```

**Solution**: Increase `timeout` in config or optimize workflow steps

### No Articles Extracted

```
Workflow execution completed: success=True, articles=0
```

**Possible causes**:
- Workflow completed but extraction not implemented
- No articles matched search criteria
- Extraction selectors need updating

## File Locations

- **Plugin**: `/src/thoth/discovery/plugins/browser_workflow_plugin.py`
- **Registration**: `/src/thoth/discovery/plugins/__init__.py`
- **Example**: `/examples/browser_workflow_plugin_example.py`
- **Documentation**: `/docs/browser_workflow_plugin.md`

## Related Components

- **BaseDiscoveryPlugin**: `/src/thoth/discovery/plugins/base.py`
- **WorkflowExecutionService**: `/src/thoth/discovery/browser/workflow_execution_service.py`
- **WorkflowEngine**: `/src/thoth/discovery/browser/workflow_engine.py`
- **BrowserManager**: `/src/thoth/discovery/browser/browser_manager.py`
- **ExtractionService**: `/src/thoth/discovery/browser/extraction_service.py`

## Future Enhancements

1. **Article extraction**: Implement extraction logic in WorkflowEngine
2. **Deduplication**: Integrate with deduplication service
3. **Relevance scoring**: Add article relevance evaluation
4. **Caching**: Cache workflow results by query parameters
5. **Parallel workflows**: Execute multiple workflows concurrently
6. **Result aggregation**: Merge results from multiple workflows
7. **Smart retry**: Retry failed extractions with different selectors

## License

Part of Project Thoth research management system.
