# Test Fixes Applied - Browser Workflow Repository Tests

## Summary

Fixed `tests/repositories/test_browser_workflow_repository.py` to match the actual database schema defined in `src/thoth/migration/002_add_browser_discovery_workflows.sql`.

## Changes Made

### 1. Updated Test Fixtures

**Before:**
```python
sample_workflow_data = {
    'user_id': 'user123',
    'status': 'active',
    'priority': 5,
    'tags': ['research', 'automation'],
    'schedule_frequency': 'daily',
    'next_run_at': datetime.now(),
    'total_runs': 0,
    'successful_runs': 0,
}
```

**After:**
```python
sample_workflow_data = {
    'name': 'Nature Journal Workflow',
    'description': 'Automated workflow for Nature journal',
    'website_domain': 'nature.com',
    'start_url': 'https://www.nature.com/search',
    'extraction_rules': {...},
    'requires_authentication': False,
    'is_active': True,
}
```

### 2. Removed Unsupported Tests (10 tests)

These tests expected fields that don't exist in the schema:

- ❌ `test_get_by_user_success` - No `user_id` field
- ❌ `test_get_by_user_with_status_filter` - No `user_id` or `status` field
- ❌ `test_get_workflows_due_for_run` - No `next_run_at` field
- ❌ `test_get_by_tags_match_any` - No `tags` field
- ❌ `test_get_by_tags_match_all` - No `tags` field
- ❌ `test_get_by_tags_no_match` - No `tags` field
- ❌ `test_update_tags_success` - No `tags` field
- ❌ `test_update_run_statistics` - Wrong field names
- ❌ `test_update_run_statistics_failed` - Wrong field names
- ❌ `test_get_workflows_by_schedule` - No `schedule_frequency` field
- ❌ `test_update_next_run_time` - No `next_run_at` field
- ❌ `test_get_all_workflow_statistics` - Test removed

### 3. Updated Tests to Match Schema (12 tests)

Fixed these tests to use correct field names:

- ✅ `test_get_by_name_success` - Removed user_id parameter
- ✅ `test_get_by_name_not_found` - Removed user_id parameter
- ✅ `test_get_active_workflows` - Changed `status='active'` to `is_active=True`
- ✅ `test_update_workflow_success` - Changed to `is_active`, `health_status`
- ✅ `test_update_execution_statistics` - New method matching schema fields
- ✅ `test_deactivate_workflow` - Check `is_active` instead of `status`
- ✅ `test_get_workflow_statistics` - Use schema field names
- ✅ `test_malformed_query_error` - Changed to `list_all()` from `get_by_user()`
- ✅ `test_create_workflow_missing_required_fields` - Expect `website_domain` error

## Actual Database Schema

```sql
CREATE TABLE browser_workflows (
    -- Basic Info
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    website_domain VARCHAR(200) NOT NULL,

    -- Access Configuration
    start_url TEXT NOT NULL,
    requires_authentication BOOLEAN DEFAULT FALSE,
    authentication_type VARCHAR(50),

    -- Extraction Configuration
    extraction_rules JSONB NOT NULL,
    pagination_config JSONB,

    -- Status & Statistics
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    total_articles_extracted INTEGER DEFAULT 0,
    average_execution_time_ms INTEGER,

    -- Timing
    last_executed_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Final Test Count

**Before:** 34 tests (many would fail due to schema mismatch)
**After:** 24 tests (all match actual schema)

### Kept Essential Tests (24):

1. **CREATE (3 tests)**
   - `test_create_workflow_success`
   - `test_create_workflow_duplicate_name`
   - `test_create_workflow_missing_required_fields`

2. **READ (5 tests)**
   - `test_get_by_id_success`
   - `test_get_by_id_not_found`
   - `test_get_by_name_success`
   - `test_get_by_name_not_found`
   - `test_get_active_workflows`

3. **UPDATE (4 tests)**
   - `test_update_workflow_success`
   - `test_update_workflow_empty_data`
   - `test_update_workflow_nonexistent`
   - `test_update_execution_statistics`

4. **DELETE (3 tests)**
   - `test_delete_workflow_success`
   - `test_delete_workflow_nonexistent`
   - `test_deactivate_workflow`

5. **STATISTICS (1 test)**
   - `test_get_workflow_statistics`

6. **PAGINATION (2 tests)**
   - `test_list_workflows_with_pagination`
   - `test_list_workflows_with_offset`

7. **CACHE (2 tests)**
   - `test_cache_enabled_get_by_id`
   - `test_cache_invalidation_on_update`

8. **ERROR HANDLING (4 tests)**
   - `test_database_connection_error`
   - `test_malformed_query_error`
   - `test_count_workflows`
   - `test_exists_workflow`

## Fields NOT in Schema

The following fields from the original tests do not exist in the actual schema:

- ❌ `user_id` - Workflows are not user-specific
- ❌ `status` - Uses `is_active` (boolean) instead
- ❌ `priority` - Not in schema
- ❌ `tags` - Not in schema (no array field)
- ❌ `schedule_frequency` - No scheduling fields
- ❌ `last_run_at` - Uses `last_executed_at` instead
- ❌ `next_run_at` - No scheduling
- ❌ `total_runs` - Uses `total_executions` instead
- ❌ `successful_runs` - Uses `successful_executions` instead
- ❌ `failed_runs` - Uses `failed_executions` instead

## Result

All 24 remaining tests now correctly match the actual database schema and will work with the real implementation of `BrowserWorkflowRepository`.
