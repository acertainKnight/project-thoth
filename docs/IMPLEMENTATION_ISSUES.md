# Browser Workflow Implementation Issues

**Date**: 2025-01-26
**Status**: CRITICAL - Core functionality NOT implemented

## Executive Summary

The browser workflow system appears complete from the API and database perspective, but **the actual browser automation and article extraction are NOT implemented**. The system will:
- ✅ Accept API requests
- ✅ Create database records
- ✅ Return "success" responses
- ❌ **NOT actually browse websites**
- ❌ **NOT extract any articles**
- ❌ **NOT perform any real work**

## Critical Issues

### 1. Article Extraction Not Implemented ⛔ BLOCKER

**File**: `src/thoth/discovery/browser/workflow_engine.py`
**Lines**: 413-441
**Severity**: CRITICAL

```python
async def _extract_articles(self, page, workflow, parameters, execution_log):
    """Extract articles from the page."""
    # TODO: Implement article extraction logic
    # This would use the extraction_rules from the workflow
    # For now, return 0
    execution_log.append({
        'timestamp': datetime.utcnow().isoformat(),
        'action': 'extraction_skipped',
        'note': 'Article extraction not yet implemented',
    })

    return 0  # ⛔ ALWAYS returns 0 articles
```

**Impact**:
- The entire purpose of the system is to extract articles
- ExtractionService class exists (528 lines) but is **never used**
- Every workflow execution returns 0 articles
- System pretends to succeed but does nothing

**What needs to happen**:
```python
# Should integrate ExtractionService like this:
extraction_service = ExtractionService(
    page,
    source_name=workflow['name'],
    existing_dois=set(),  # Load from database
    existing_titles=set()
)

articles = await extraction_service.extract_articles(
    extraction_rules=workflow['extraction_rules'],
    max_articles=parameters.get('max_articles', 100)
)

return len(articles)
```

---

### 2. Authentication Not Implemented ⛔ BLOCKER

**File**: `src/thoth/discovery/browser/workflow_engine.py`
**Lines**: 320-333
**Severity**: CRITICAL for authenticated sites

```python
async def _authenticate(self, page, workflow, execution_log):
    """Handle authentication if required."""
    # TODO: Implement authentication logic
    # For now, just log that authentication would be performed
    auth_type = workflow.get('authentication_type', 'unknown')

    execution_log.append({
        'timestamp': datetime.utcnow().isoformat(),
        'action': 'authentication_skipped',
        'auth_type': auth_type,
        'note': 'Authentication not yet implemented',
    })

    logger.warning(f'Authentication required but not implemented: {auth_type}')
```

**Impact**:
- Any workflow requiring authentication will silently fail
- No credentials are retrieved from `workflow_credentials` table
- No authentication is performed
- Workflow continues anyway and fails later

**What needs to happen**:
1. Retrieve credentials from `WorkflowCredentialsRepository`
2. Decrypt credentials using encryption key
3. Implement authentication strategies (form login, OAuth, API key, etc.)
4. Store session state using Playwright's storage state feature
5. Verify authentication succeeded before continuing

---

### 3. Workflow Execution is Fake ⛔ BLOCKER

**File**: `src/thoth/server/routers/browser_workflows.py`
**Lines**: 473-546
**Severity**: CRITICAL

```python
@router.post("/{workflow_id}/execute")
async def execute_workflow(...):
    """Execute a workflow asynchronously with provided parameters."""

    # Creates execution record
    execution_id = await executions_repo.create(execution_data)

    # TODO: Queue execution task asynchronously (e.g., with Celery, background task)
    # For now, return the execution ID immediately
    # The actual execution would happen in a background worker

    return WorkflowExecutionResponse(
        execution_id=execution_id,
        workflow_id=workflow_id,
        status="pending",
        message="Workflow execution queued successfully"  # ⛔ LIE - Nothing queued
    )
```

**Impact**:
- API says "queued successfully" but nothing is queued
- Execution record stays in "pending" state forever
- No actual browser automation happens
- No background task system exists

**What needs to happen**:
1. Implement background task system (Celery, Dramatiq, or FastAPI BackgroundTasks)
2. Queue actual execution task
3. Task worker calls `WorkflowExecutionService.execute_workflow()`
4. Update execution status as task progresses
5. Store results in database

---

### 4. MCP Tool Execution is Fake ⛔ BLOCKER

**File**: `src/thoth/mcp/tools/browser_workflow_tools.py`
**Lines**: 427-531
**Severity**: CRITICAL

```python
class ExecuteWorkflowMCPTool(MCPTool):
    async def execute(self, arguments):
        # ... validation ...

        # TODO: This is a placeholder for actual browser automation
        # In production, this would use Playwright/Selenium to execute the workflow
        result_text = f"""✓ Workflow execution initiated!

**Workflow:** {workflow['name']}
...

⚠️ Note: Full browser automation requires Playwright integration.
This is a placeholder response. Actual execution would:
1. Launch browser session
2. Execute {len(actions)} action steps
3. Extract articles using search config
4. Store results in database
```

**Impact**:
- MCP tool says "execution initiated" but does nothing
- Agent thinks workflow succeeded
- Returns fake success with 0 articles
- Misleading to users and agents

**What needs to happen**:
- Remove placeholder
- Actually call `WorkflowExecutionService.execute_workflow()`
- Return real results

---

### 5. WorkflowExecutionService Returns Empty Results

**File**: `src/thoth/discovery/browser/workflow_execution_service.py`
**Lines**: 225-265
**Severity**: CRITICAL

```python
# Execute workflow through engine
# Note: WorkflowEngine currently doesn't extract articles yet
# (based on TODO comments in the code)
workflow_result = await self.workflow_engine.execute_workflow(...)

# ...

# For now, return empty articles list since extraction is not yet implemented
# When extraction is implemented in WorkflowEngine, this will contain actual articles
articles: list[ScrapedArticleMetadata] = []

return WorkflowExecutionOutput(
    articles=articles,  # ⛔ Always empty
    stats=stats,
    execution_log=workflow_result.execution_log or [],
)
```

**Impact**:
- Service acknowledges extraction isn't implemented
- Returns empty articles list
- Stats show 0 articles extracted
- System appears to work but produces no output

---

## Non-Critical Issues

### 6. ActionExecutor Not Integrated

**File**: `src/thoth/discovery/browser/action_executor.py`
**Status**: Implemented but unused

The `ActionExecutor` class (405 lines) with retry logic, parameter substitution, and multi-strategy element selection exists but is **never instantiated or used** by `WorkflowEngine`.

**What needs to happen**:
- WorkflowEngine should use ActionExecutor to execute workflow_actions
- Currently only handles basic navigation and parameter injection

---

### 7. No Background Task System

**Impact**:
- Long-running workflows will timeout HTTP requests
- No way to monitor progress
- No queue system for handling multiple executions

**What needs to happen**:
- Implement Celery or equivalent task queue
- Add task status tracking
- Implement progress updates via WebSocket or polling

---

### 8. No Session Management for Authentication

**Impact**:
- Every execution would need to authenticate from scratch
- Slower execution
- Risk of rate limiting

**What needs to happen**:
- Use Playwright's storage state to save/restore sessions
- Cache authentication state per workflow
- Refresh sessions when expired

---

### 9. WorkflowCredentialsRepository Missing Encryption

**File**: Database schema defines `workflow_credentials` table
**Status**: Table exists but no encryption key management

**What needs to happen**:
- Implement encryption key management (environment variable or secrets manager)
- Encrypt credentials before storage
- Decrypt credentials during retrieval

---

## What Actually Works

✅ Database schema and migrations
✅ Repository pattern with caching
✅ REST API endpoints (structure only)
✅ MCP tools (structure only)
✅ Discovery plugin registration
✅ Pydantic schemas and validation
✅ ExtractionService (code exists, just not integrated)
✅ ActionExecutor (code exists, just not integrated)

---

## What Doesn't Work

❌ **Article extraction** - Core functionality
❌ **Browser automation** - No actual browsing
❌ **Authentication** - Stub only
❌ **Workflow execution** - Returns fake success
❌ **Background tasks** - No queue system
❌ **MCP tool execution** - Placeholder only
❌ **Action recording** - Not integrated
❌ **Credentials encryption** - Not implemented

---

## Summary

This implementation is approximately **40% complete**:

- **Infrastructure**: 90% complete (database, API, schemas)
- **Core functionality**: 0% complete (no actual browsing or extraction)
- **Integration**: 20% complete (services exist but not wired together)

The system will accept requests, create database records, and return "success" responses, but **will not extract any articles or perform any actual work**.

To make this production-ready, the following must be implemented:

1. ⛔ **BLOCKER**: Integrate ExtractionService into WorkflowEngine._extract_articles()
2. ⛔ **BLOCKER**: Implement authentication in WorkflowEngine._authenticate()
3. ⛔ **BLOCKER**: Implement background task queue for async execution
4. ⛔ **BLOCKER**: Wire up MCP tool to call real execution service
5. ⛔ **BLOCKER**: Integrate ActionExecutor for recorded workflow actions
6. ⚠️ **IMPORTANT**: Implement credentials encryption
7. ⚠️ **IMPORTANT**: Add session management for authentication
8. ⚠️ **IMPORTANT**: Add progress tracking and status updates

**Estimated work remaining**: 2-3 full days of implementation
