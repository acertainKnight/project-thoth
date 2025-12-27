# BrowserWorkflowRepository Fix Summary

## Date: 2025-12-26

## Issues Fixed

### 1. Schema Alignment ✅
- **Verified**: No `user_id` field in database schema - workflows are system-wide sources
- **Verified**: No `tags` field in database schema
- **Result**: Repository methods correctly match the actual schema

### 2. Missing Method Added ✅

#### `get_workflows_due_for_run(hours_since_last_run: int = 24)`
**Purpose**: Return workflows that need to be executed based on schedule

**Logic**:
- Returns active workflows (`is_active = true`)
- Where `last_executed_at` is NULL (never run) OR older than specified hours
- Orders by `last_executed_at ASC NULLS FIRST` (prioritizes never-run workflows)
- Default: 24 hours (daily schedule)
- Caching: 5 minutes TTL (time-sensitive data)

**Query**:
```sql
SELECT * FROM browser_workflows
WHERE is_active = true
  AND (
    last_executed_at IS NULL
    OR last_executed_at < NOW() - ($1 || ' hours')::INTERVAL
  )
ORDER BY
    last_executed_at ASC NULLS FIRST,
    name ASC
```

### 3. Existing Method Verified ✅

#### `update_statistics(workflow_id, success, articles_found, duration_ms)`
**Status**: Already exists in repository (lines 229-295)

**Purpose**: Update execution statistics after workflow runs

**Features**:
- Updates execution counters (`total_executions`, `successful_executions`, `failed_executions`)
- Tracks article extraction (`total_articles_extracted`)
- Calculates running average execution time
- Updates timestamps (`last_executed_at`, `last_success_at`, `last_failure_at`)
- Invalidates cache after update
- Proper error handling and logging

## Methods NOT Added (Schema Mismatch)

These were explicitly excluded because the database schema doesn't support them:

- ❌ `get_by_user()` - No `user_id` column in `browser_workflows` table
- ❌ `get_by_tags()` - No `tags` column in `browser_workflows` table
- ❌ `update_tags()` - No `tags` column in `browser_workflows` table

## Current Method Summary

### CRUD Operations
- `create(workflow_data)` - Create new workflow
- `get_by_id(workflow_id)` - Get by UUID
- `get_by_name(name)` - Get by unique name
- `update(workflow_id, updates)` - Update fields
- `delete(workflow_id)` - Delete workflow

### Query Methods
- `get_active_workflows()` - All active workflows
- `get_by_domain(domain)` - Filter by website domain
- `get_workflows_due_for_run(hours)` - ✨ NEW - Workflows needing execution

### Statistics & Health
- `update_statistics(workflow_id, success, articles_found, duration_ms)` - Update execution stats
- `update_health_status(workflow_id, status)` - Set health status
- `get_statistics()` - Aggregated statistics across all workflows

### Status Management
- `activate(workflow_id)` - Enable workflow
- `deactivate(workflow_id)` - Disable workflow

## Database Schema Reference

### `browser_workflows` Table
```sql
CREATE TABLE browser_workflows (
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    website_domain VARCHAR(200) NOT NULL,
    start_url TEXT NOT NULL,
    requires_authentication BOOLEAN DEFAULT FALSE,
    authentication_type VARCHAR(50),
    extraction_rules JSONB NOT NULL,
    pagination_config JSONB,
    max_articles_per_run INTEGER DEFAULT 100,
    timeout_seconds INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    total_articles_extracted INTEGER DEFAULT 0,
    average_execution_time_ms INTEGER,
    last_executed_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Testing Recommendations

1. **Test `get_workflows_due_for_run()`**:
   ```python
   # Should return workflows never run or run >24h ago
   due_workflows = await repo.get_workflows_due_for_run(hours_since_last_run=24)

   # Should return workflows run >1h ago
   recent_due = await repo.get_workflows_due_for_run(hours_since_last_run=1)
   ```

2. **Test `update_statistics()`**:
   ```python
   # Test successful execution
   success = await repo.update_statistics(
       workflow_id=uuid,
       success=True,
       articles_found=42,
       duration_ms=15000
   )

   # Test failed execution
   failure = await repo.update_statistics(
       workflow_id=uuid,
       success=False,
       articles_found=0,
       duration_ms=5000
   )
   ```

## Cache Strategy

- **General queries**: Default TTL from BaseRepository
- **Time-sensitive** (`get_workflows_due_for_run`): 5 minutes TTL
- **All updates**: Invalidate cache for affected workflow

## Architecture Notes

1. **System-wide sources**: Workflows are NOT user-specific - they are shared discovery sources
2. **Scheduled execution**: Use `get_workflows_due_for_run()` in scheduler/cron job
3. **Statistics tracking**: Call `update_statistics()` after each workflow execution
4. **Health monitoring**: Health status automatically updated by database triggers based on failure patterns

## Files Modified

- `/src/thoth/repositories/browser_workflow_repository.py` - Added `get_workflows_due_for_run()` method

## References

- Migration: `/src/thoth/migration/002_add_browser_discovery_workflows.sql`
- Documentation: `/docs/plans/COMPREHENSIVE_BROWSER_DISCOVERY_PLAN.md`
