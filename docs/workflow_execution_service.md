# WorkflowExecutionService

High-level service for executing browser-based article discovery workflows.

## Overview

The `WorkflowExecutionService` provides a simple, unified interface for executing browser workflows by coordinating the `BrowserManager`, `WorkflowEngine`, and `ExtractionService`. It handles all dependency initialization, parameter validation, and result aggregation.

## Features

- **Simple API**: Single `execute_workflow()` method for easy usage
- **Dependency Injection**: Constructor injection for testability
- **Parameter Validation**: Validates execution parameters before execution
- **Automatic Initialization**: Handles browser manager and engine setup
- **Statistics Tracking**: Returns detailed execution statistics
- **Error Handling**: Graceful error handling with detailed error messages
- **Resource Management**: Automatic cleanup of browser resources

## Architecture

```
WorkflowExecutionService
├── BrowserManager (browser lifecycle)
├── WorkflowEngine (workflow orchestration)
├── ExtractionService (article extraction)
└── Repositories
    ├── BrowserWorkflowRepository
    ├── WorkflowSearchConfigRepository
    └── WorkflowExecutionsRepository
```

## Usage

### Basic Example

```python
from uuid import UUID
from thoth.config import config
from thoth.discovery.browser import WorkflowExecutionService
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas.browser_workflow import ExecutionParameters

# Initialize PostgreSQL service
postgres_service = PostgresService(config=config)
await postgres_service.initialize()

# Create workflow execution service
service = WorkflowExecutionService(
    postgres_service=postgres_service,
    max_concurrent_browsers=5,
    default_timeout=30000,
    max_retries=3
)

# Initialize service
await service.initialize()

# Execute workflow
result = await service.execute_workflow(
    workflow_id=UUID('...'),
    parameters=ExecutionParameters(
        keywords=['machine learning', 'neural networks'],
        date_range='last_7d'
    ),
    max_articles=100
)

# Use results
print(f"Extracted {len(result.articles)} articles")
print(f"Success: {result.stats.success}")
print(f"Duration: {result.stats.duration_ms}ms")

# Cleanup
await service.shutdown()
await postgres_service.shutdown()
```

### Advanced Example with Error Handling

```python
try:
    # Initialize service
    service = WorkflowExecutionService(postgres_service)
    await service.initialize()

    # Get workflow info first
    workflow_info = await service.get_workflow_info(workflow_id)
    if not workflow_info:
        raise ValueError("Workflow not found")

    print(f"Executing workflow: {workflow_info['name']}")

    # Execute with custom parameters
    result = await service.execute_workflow(
        workflow_id=workflow_id,
        parameters=ExecutionParameters(
            keywords=['quantum computing', 'qubits'],
            date_range='last_30d',
            subject='Physics',
            custom_filters={'journal': 'Nature'}
        ),
        trigger=ExecutionTrigger.SCHEDULED,
        max_articles=50
    )

    # Check results
    if result.stats.success:
        print(f"Successfully extracted {len(result.articles)} articles")

        # Process articles
        for article in result.articles:
            print(f"Title: {article.title}")
            print(f"DOI: {article.doi}")
            print(f"Authors: {', '.join(article.authors)}")
            print()
    else:
        print(f"Execution failed: {result.stats.error_message}")

    # Print statistics
    print(f"\nStatistics:")
    print(f"  Extracted: {result.stats.articles_extracted}")
    print(f"  Skipped: {result.stats.articles_skipped}")
    print(f"  Errors: {result.stats.articles_errors}")
    print(f"  Duration: {result.stats.duration_ms}ms")

except WorkflowExecutionServiceError as e:
    print(f"Service error: {e}")
finally:
    await service.shutdown()
```

### List Active Workflows

```python
# Get all active workflows
workflows = await service.list_active_workflows()

for workflow in workflows:
    print(f"ID: {workflow['id']}")
    print(f"Name: {workflow['name']}")
    print(f"Domain: {workflow['website_domain']}")
    print(f"Success Rate: {workflow.get('success_rate', 0):.2%}")
    print()
```

## API Reference

### WorkflowExecutionService

#### Constructor

```python
WorkflowExecutionService(
    postgres_service: PostgresService,
    max_concurrent_browsers: int = 5,
    default_timeout: int = 30000,
    max_retries: int = 3
)
```

**Parameters:**
- `postgres_service`: PostgreSQL service for database operations
- `max_concurrent_browsers`: Maximum concurrent browser instances (default: 5)
- `default_timeout`: Default timeout in milliseconds (default: 30000)
- `max_retries`: Maximum retry attempts for failed actions (default: 3)

#### Methods

##### `initialize()`

```python
async def initialize() -> None
```

Initialize the service and its dependencies. Must be called before executing workflows.

**Raises:**
- `WorkflowExecutionServiceError`: If initialization fails

##### `shutdown()`

```python
async def shutdown() -> None
```

Shutdown the service and cleanup resources. Should be called when done using the service.

##### `execute_workflow()`

```python
async def execute_workflow(
    workflow_id: UUID,
    parameters: ExecutionParameters,
    trigger: ExecutionTrigger = ExecutionTrigger.MANUAL,
    query_id: UUID | None = None,
    max_articles: int = 100
) -> WorkflowExecutionOutput
```

Execute a workflow with given parameters and return extracted articles.

**Parameters:**
- `workflow_id`: UUID of the workflow to execute
- `parameters`: Execution parameters (keywords, filters, date ranges)
- `trigger`: What triggered this execution (manual, scheduled, query)
- `query_id`: Optional research question ID if triggered by query
- `max_articles`: Maximum number of articles to extract (default: 100)

**Returns:**
- `WorkflowExecutionOutput`: Contains extracted articles and execution stats

**Raises:**
- `WorkflowExecutionServiceError`: If execution fails or service not initialized

##### `get_workflow_info()`

```python
async def get_workflow_info(workflow_id: UUID) -> dict[str, Any] | None
```

Get workflow information without executing it.

**Returns:**
- Workflow configuration dict or None if not found

##### `list_active_workflows()`

```python
async def list_active_workflows() -> list[dict[str, Any]]
```

List all active workflows.

**Returns:**
- List of active workflow configurations

#### Properties

##### `is_initialized`

```python
@property
def is_initialized(self) -> bool
```

Check if service is initialized and ready.

### Data Classes

#### WorkflowExecutionOutput

```python
@dataclass
class WorkflowExecutionOutput:
    articles: list[ScrapedArticleMetadata]
    stats: WorkflowExecutionStats
    execution_log: list[dict[str, Any]]
```

Output from workflow execution containing articles and statistics.

#### WorkflowExecutionStats

```python
@dataclass
class WorkflowExecutionStats:
    execution_id: UUID
    success: bool
    articles_count: int
    articles_extracted: int
    articles_skipped: int
    articles_errors: int
    duration_ms: int
    pages_visited: int
    error_message: str | None = None
```

Statistics from workflow execution.

#### ExecutionParameters

```python
class ExecutionParameters(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    date_range: str | None = None
    subject: str | None = None
    custom_filters: dict[str, Any] = Field(default_factory=dict)
```

Parameters for workflow execution.

**Common date_range values:**
- `'last_24h'`: Last 24 hours
- `'last_7d'`: Last 7 days
- `'last_30d'`: Last 30 days
- `'last_90d'`: Last 90 days
- `'last_year'`: Last year
- `'custom'`: Custom date range (use custom_filters)

## Error Handling

The service provides detailed error messages and graceful failure handling:

```python
try:
    result = await service.execute_workflow(workflow_id, parameters)

    if not result.stats.success:
        print(f"Execution failed: {result.stats.error_message}")
        # Check execution log for details
        for log_entry in result.execution_log:
            if log_entry.get('action') == 'error':
                print(f"Error: {log_entry.get('error')}")

except WorkflowExecutionServiceError as e:
    print(f"Service error: {e}")
```

## Integration with Research Queries

The service can be triggered by research queries:

```python
result = await service.execute_workflow(
    workflow_id=workflow_id,
    parameters=parameters,
    trigger=ExecutionTrigger.QUERY,
    query_id=research_question_id
)
```

## Performance Considerations

- **Concurrent Browsers**: Limit concurrent browsers to avoid resource exhaustion
- **Timeout Configuration**: Adjust timeout based on website response times
- **Retry Strategy**: Configure retries based on website reliability
- **Max Articles**: Limit article count to prevent long-running executions

## Future Enhancements

The service is designed to support future features:

1. **Real-time Extraction**: Currently workflow engine has extraction placeholder
2. **Progress Callbacks**: Streaming updates during execution
3. **Advanced Filtering**: Post-extraction filtering and deduplication
4. **Caching**: Cache workflow results for repeated queries
5. **Batch Execution**: Execute multiple workflows in parallel

## Testing

```python
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_workflow_execution():
    # Mock dependencies
    postgres_service = AsyncMock()

    # Create service
    service = WorkflowExecutionService(postgres_service)
    await service.initialize()

    # Test execution
    result = await service.execute_workflow(
        workflow_id=UUID('...'),
        parameters=ExecutionParameters(keywords=['test'])
    )

    assert result.stats.success
    assert len(result.articles) >= 0

    await service.shutdown()
```

## See Also

- [WorkflowEngine Documentation](./workflow_engine.md)
- [BrowserManager Documentation](./browser_manager.md)
- [ExtractionService Documentation](./extraction_service.md)
- [Example Script](../examples/workflow_execution_example.py)
