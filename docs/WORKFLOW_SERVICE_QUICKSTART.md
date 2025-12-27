# WorkflowExecutionService Quick Start

## 5-Minute Quick Start Guide

### Installation
```bash
# Already included in project dependencies
# No additional installation needed
```

### Basic Usage

```python
from uuid import UUID
from thoth.config import config
from thoth.discovery.browser import WorkflowExecutionService
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas.browser_workflow import ExecutionParameters

# 1. Initialize services
postgres = PostgresService(config=config)
await postgres.initialize()

service = WorkflowExecutionService(postgres)
await service.initialize()

# 2. Execute workflow
result = await service.execute_workflow(
    workflow_id=UUID('your-workflow-id'),
    parameters=ExecutionParameters(
        keywords=['machine learning', 'neural networks'],
        date_range='last_7d'
    )
)

# 3. Use results
print(f"Success: {result.stats.success}")
print(f"Articles: {len(result.articles)}")
print(f"Duration: {result.stats.duration_ms}ms")

for article in result.articles:
    print(f"- {article.title}")

# 4. Cleanup
await service.shutdown()
await postgres.shutdown()
```

## Common Patterns

### Pattern 1: List and Execute Workflows
```python
# Get available workflows
workflows = await service.list_active_workflows()

# Execute first workflow
if workflows:
    result = await service.execute_workflow(
        workflow_id=workflows[0]['id'],
        parameters=ExecutionParameters(keywords=['AI'])
    )
```

### Pattern 2: Error Handling
```python
try:
    result = await service.execute_workflow(workflow_id, parameters)

    if result.stats.success:
        # Process articles
        process_articles(result.articles)
    else:
        # Handle failure
        logger.error(f"Failed: {result.stats.error_message}")

except WorkflowExecutionServiceError as e:
    logger.error(f"Service error: {e}")
```

### Pattern 3: Custom Parameters
```python
parameters = ExecutionParameters(
    keywords=['quantum computing', 'qubits'],
    date_range='last_30d',
    subject='Physics',
    custom_filters={
        'journal': 'Nature',
        'min_citations': 10
    }
)

result = await service.execute_workflow(workflow_id, parameters)
```

### Pattern 4: Integration with Research Questions
```python
# Triggered by research question
result = await service.execute_workflow(
    workflow_id=workflow_id,
    parameters=ExecutionParameters(
        keywords=research_question.keywords,
        date_range='last_30d'
    ),
    trigger=ExecutionTrigger.QUERY,
    query_id=research_question.id,
    max_articles=100
)
```

## Common Parameters

### ExecutionParameters
```python
ExecutionParameters(
    keywords=['term1', 'term2'],           # Search keywords
    date_range='last_7d',                   # Date range filter
    subject='Computer Science',             # Subject area
    custom_filters={'key': 'value'}        # Custom filters
)
```

### Date Range Options
- `'last_24h'` - Last 24 hours
- `'last_7d'` - Last 7 days
- `'last_30d'` - Last 30 days
- `'last_90d'` - Last 90 days
- `'last_year'` - Last year
- `'custom'` - Use custom_filters for dates

## Result Structure

```python
result.articles              # List[ScrapedArticleMetadata]
result.stats.success         # bool
result.stats.articles_count  # int
result.stats.duration_ms     # int
result.stats.error_message   # Optional[str]
result.execution_log         # List[dict]
```

## Service Configuration

```python
service = WorkflowExecutionService(
    postgres_service=postgres,
    max_concurrent_browsers=5,    # Browser pool size
    default_timeout=30000,         # Timeout in ms
    max_retries=3                  # Retry attempts
)
```

## Error Handling

### Service Errors
```python
from thoth.discovery.browser import WorkflowExecutionServiceError

try:
    result = await service.execute_workflow(workflow_id, parameters)
except WorkflowExecutionServiceError as e:
    # Service-level error (initialization, validation)
    handle_service_error(e)
```

### Execution Errors
```python
result = await service.execute_workflow(workflow_id, parameters)

if not result.stats.success:
    # Workflow-level error (browser, extraction)
    error = result.stats.error_message
    handle_execution_error(error)
```

## Tips & Best Practices

### 1. Always Initialize
```python
# ❌ Bad
service = WorkflowExecutionService(postgres)
result = await service.execute_workflow(...)  # Error!

# ✅ Good
service = WorkflowExecutionService(postgres)
await service.initialize()
result = await service.execute_workflow(...)
```

### 2. Always Cleanup
```python
# ✅ Good
try:
    await service.initialize()
    result = await service.execute_workflow(...)
finally:
    await service.shutdown()
```

### 3. Check Success Status
```python
# ✅ Good
result = await service.execute_workflow(...)
if result.stats.success:
    process_articles(result.articles)
else:
    log_error(result.stats.error_message)
```

### 4. Validate Before Execution
```python
# ✅ Good
workflow = await service.get_workflow_info(workflow_id)
if not workflow:
    raise ValueError("Workflow not found")

if not workflow['is_active']:
    raise ValueError("Workflow is inactive")

result = await service.execute_workflow(workflow_id, parameters)
```

## Troubleshooting

### Problem: "Service not initialized"
**Solution**: Call `await service.initialize()` before using

### Problem: "At least keywords or custom_filters must be provided"
**Solution**: Provide either keywords list or custom_filters dict

### Problem: Browser timeout
**Solution**: Increase timeout in service configuration
```python
service = WorkflowExecutionService(
    postgres,
    default_timeout=60000  # 60 seconds
)
```

### Problem: Too many concurrent browsers
**Solution**: Reduce max_concurrent_browsers
```python
service = WorkflowExecutionService(
    postgres,
    max_concurrent_browsers=3
)
```

## Next Steps

1. **Read Full Documentation**: See `docs/workflow_execution_service.md`
2. **Run Example**: Try `examples/workflow_execution_example.py`
3. **View Tests**: Check `tests/test_workflow_execution_service.py`
4. **Integrate**: Add to your research questions workflow

## Support

- **Documentation**: `/docs/workflow_execution_service.md`
- **Examples**: `/examples/workflow_execution_example.py`
- **Tests**: `/tests/test_workflow_execution_service.py`
- **Source**: `/src/thoth/discovery/browser/workflow_execution_service.py`
