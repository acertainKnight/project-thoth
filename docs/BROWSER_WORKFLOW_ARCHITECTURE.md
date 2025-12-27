# Browser Workflow Tools - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI Agent                                 │
│  (Requests browser workflow creation and management)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ MCP Protocol
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    MCP Server (server.py)                        │
│  - Protocol handling                                             │
│  - Transport management (HTTP, SSE, stdio)                       │
│  - Tool registry                                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │
┌────────────────────────▼────────────────────────────────────────┐
│              MCPToolRegistry (base_tools.py)                     │
│  - Tool registration                                             │
│  - Tool lookup                                                   │
│  - Tool execution                                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │
┌────────────────────────▼────────────────────────────────────────┐
│        Browser Workflow Tools (browser_workflow_tools.py)        │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  1. CreateBrowserWorkflowMCPTool                       │    │
│  │     - Create new workflow                              │    │
│  │     → BrowserWorkflowRepository                        │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  2. AddWorkflowActionMCPTool                           │    │
│  │     - Add action steps                                 │    │
│  │     → WorkflowActionsRepository                        │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  3. ConfigureSearchMCPTool                             │    │
│  │     - Configure result extraction                      │    │
│  │     → WorkflowSearchConfigRepository                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  4. ExecuteWorkflowMCPTool                             │    │
│  │     - Execute workflow                                 │    │
│  │     → All repositories + statistics                    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  5. ListWorkflowsMCPTool                               │    │
│  │     - List all workflows                               │    │
│  │     → BrowserWorkflowRepository                        │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  6. GetWorkflowDetailsMCPTool                          │    │
│  │     - Get detailed info                                │    │
│  │     → All workflow repositories                        │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  7. UpdateWorkflowStatusMCPTool                        │    │
│  │     - Activate/deactivate                              │    │
│  │     → BrowserWorkflowRepository                        │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  8. DeleteWorkflowMCPTool                              │    │
│  │     - Delete workflow                                  │    │
│  │     → BrowserWorkflowRepository (cascade)              │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ service_manager.postgres
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  Service Manager                                 │
│  - PostgresService                                               │
│  - Dependency injection                                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  Repository Layer                                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  BrowserWorkflowRepository                           │      │
│  │  - CRUD operations                                   │      │
│  │  - Statistics tracking                               │      │
│  │  - Health management                                 │      │
│  │  - Caching                                           │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  WorkflowActionsRepository                           │      │
│  │  - Action CRUD                                       │      │
│  │  - Step ordering                                     │      │
│  │  - Action queries                                    │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  WorkflowSearchConfigRepository                      │      │
│  │  - Config CRUD                                       │      │
│  │  - Selector validation                               │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  WorkflowExecutionsRepository                        │      │
│  │  - Execution history                                 │      │
│  │  - Metrics tracking                                  │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ SQL Queries
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  PostgreSQL Database                             │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  browser_workflows                                   │      │
│  │  - id (UUID, PK)                                     │      │
│  │  - name, domain, start_url                           │      │
│  │  - is_active, health_status                          │      │
│  │  - statistics (executions, articles, timing)         │      │
│  │  - timestamps                                        │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  workflow_actions                                    │      │
│  │  - id (UUID, PK)                                     │      │
│  │  - workflow_id (FK) → browser_workflows             │      │
│  │  - step_number, action_type                          │      │
│  │  - selector, value, config                           │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  workflow_search_config                              │      │
│  │  - id (UUID, PK)                                     │      │
│  │  - workflow_id (FK, UNIQUE) → browser_workflows     │      │
│  │  - selectors (result, title, url, snippet)          │      │
│  │  - max_results, pagination_config                    │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  workflow_executions                                 │      │
│  │  - id (UUID, PK)                                     │      │
│  │  - workflow_id (FK) → browser_workflows             │      │
│  │  - execution_start, execution_end                    │      │
│  │  - status, articles_found, errors                    │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

### Workflow Creation Flow

```
AI Agent
   │
   │ create_browser_workflow
   │ {name, domain, start_url}
   │
   ▼
CreateBrowserWorkflowMCPTool
   │
   │ validate input
   │ prepare workflow_data
   │
   ▼
BrowserWorkflowRepository
   │
   │ INSERT INTO browser_workflows
   │
   ▼
PostgreSQL
   │
   │ RETURNING id
   │
   ▼
Response to AI Agent
{workflow_id: "550e8400-..."}
```

### Action Addition Flow

```
AI Agent
   │
   │ add_workflow_action
   │ {workflow_id, action_type, selector}
   │
   ▼
AddWorkflowActionMCPTool
   │
   │ get current step count
   │ auto-increment step_number
   │
   ▼
WorkflowActionsRepository
   │
   │ INSERT INTO workflow_actions
   │
   ▼
PostgreSQL
   │
   │ RETURNING id
   │ invalidate cache
   │
   ▼
Response to AI Agent
{action_id: "660e8400-..."}
```

### Workflow Execution Flow

```
AI Agent
   │
   │ execute_workflow
   │ {workflow_id, keywords, max_articles}
   │
   ▼
ExecuteWorkflowMCPTool
   │
   ├─→ BrowserWorkflowRepository
   │   └─ get_by_id(workflow_id)
   │
   ├─→ WorkflowActionsRepository
   │   └─ get_by_workflow_id(workflow_id)
   │
   ├─→ WorkflowSearchConfigRepository
   │   └─ get_by_workflow_id(workflow_id)
   │
   │ validate workflow is active
   │ validate actions exist
   │
   │ [Future: Execute with Playwright]
   │ - Launch browser
   │ - Execute actions sequentially
   │ - Extract results with selectors
   │ - Store articles
   │
   ├─→ BrowserWorkflowRepository
   │   └─ update_statistics(...)
   │
   ▼
Response to AI Agent
{articles_found: 0, duration_ms: 145}
```

## Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                        AI Agent                              │
└────┬────────────────────────────────────────────────────────┘
     │
     │ Uses all 8 tools
     │
┌────▼─────────┬──────────┬──────────┬──────────┬────────────┐
│              │          │          │          │            │
▼              ▼          ▼          ▼          ▼            ▼
Create      Add       Configure  Execute   List      Get Details
Workflow    Actions   Search              Workflows
│              │          │          │          │            │
└──────┬───────┴──────┬───┴────┬─────┴─────┬────┴────────────┘
       │              │        │           │
       │              │        │           │
┌──────▼──────────────▼────────▼───────────▼─────────────────┐
│                Repository Layer                              │
│  - BrowserWorkflowRepository                                 │
│  - WorkflowActionsRepository                                 │
│  - WorkflowSearchConfigRepository                            │
│  - WorkflowExecutionsRepository                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                     PostgreSQL Database
```

## Tool Dependencies

```
create_browser_workflow
    ↓
    Creates workflow record
    ↓
add_workflow_action (multiple times)
    ↓
    Adds action steps 1, 2, 3, ...
    ↓
configure_search
    ↓
    Configures result extraction
    ↓
execute_workflow
    ↓
    Executes workflow and extracts results
    ↓
list_workflows / get_workflow_details
    ↓
    Monitor and review results
    ↓
update_workflow_status (if needed)
    ↓
    Activate/deactivate based on performance
    ↓
delete_workflow (if obsolete)
```

## Error Handling Flow

```
AI Agent Request
    ↓
MCP Tool
    ↓
Try Block
    │
    ├─ Success Path
    │   └─> MCPToolCallResult(content=[...])
    │
    └─ Exception Path
        └─> self.handle_error(e)
            └─> MCPToolCallResult(content=[...], isError=True)
    ↓
Response to AI Agent
```

## Caching Strategy

```
Repository Layer
    │
    ├─ Check cache first
    │   │
    │   ├─ Cache HIT → Return cached data
    │   │
    │   └─ Cache MISS → Query database
    │                  → Store in cache
    │                  → Return data
    │
    └─ Invalidate cache on:
        - Create operations
        - Update operations
        - Delete operations
```

## Workflow State Machine

```
                    ┌─────────────┐
                    │   Created   │
                    │ (is_active) │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐
    │   Actions   │ │  Search   │ │   Ready     │
    │    Added    │ │ Configured│ │ (No config) │
    └──────┬──────┘ └─────┬─────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │  Executable │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐
    │  Executing  │ │   Active  │ │  Inactive   │
    │   (Running) │ │(Can run)  │ │(Paused)     │
    └──────┬──────┘ └─────┬─────┘ └──────┬──────┘
           │               │               │
    ┌──────▼──────┐       │        ┌──────▼──────┐
    │  Success/   │       │        │  Activate/  │
    │   Failure   │       │        │ Deactivate  │
    └──────┬──────┘       │        └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │   Deleted   │
                    │  (Cascade)  │
                    └─────────────┘
```

## Integration Points

```
Browser Workflow Tools
    │
    ├─→ Research Question Service
    │   └─ Use query criteria for filtering
    │
    ├─→ Discovery Service
    │   └─ Complement API-based discovery
    │
    ├─→ Article Service
    │   └─ Process extracted articles
    │
    ├─→ Processing Service
    │   └─ Extract PDF content
    │
    └─→ Tag Service
        └─ Auto-tag discovered articles
```

## Technology Stack

```
┌─────────────────────────────────────────────────┐
│ AI Agent (Claude, GPT-4, etc.)                  │
└─────────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────┐
│ MCP Protocol (JSON-RPC over HTTP/SSE/stdio)     │
└─────────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────┐
│ Python 3.12+                                     │
│ - asyncio (async/await)                          │
│ - loguru (logging)                               │
│ - pydantic (validation)                          │
└─────────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────┐
│ PostgreSQL Database                              │
│ - JSONB support                                  │
│ - UUID primary keys                              │
│ - Foreign key constraints                        │
│ - Cascade deletes                                │
└─────────────────────────────────────────────────┘
                     │
┌─────────────────────────────────────────────────┐
│ Future: Playwright/Selenium                      │
│ - Browser automation                             │
│ - Screenshot capture                             │
│ - JavaScript execution                           │
└─────────────────────────────────────────────────┘
```

## Performance Considerations

```
Request → MCP Server
              │
              ├─ Tool Lookup (O(1) - dict)
              │
              ├─ Input Validation (O(n) - fields)
              │
              ├─ Cache Check (O(1) - dict)
              │   │
              │   ├─ HIT → Return (fast)
              │   │
              │   └─ MISS → Database Query
              │              │
              │              ├─ Index Lookup (O(log n))
              │              │
              │              └─ Cache Store
              │
              └─ Response (O(1))
```

## Security Boundaries

```
┌─────────────────────────────────────────────────┐
│ AI Agent (Untrusted Input)                      │
└─────────────────────┬───────────────────────────┘
                      │
                      │ MCP Protocol
                      │
┌─────────────────────▼───────────────────────────┐
│ Input Validation Layer                          │
│ - JSON Schema validation                         │
│ - UUID validation                                │
│ - SQL injection prevention                       │
│ - XSS prevention (future)                        │
└─────────────────────┬───────────────────────────┘
                      │
                      │
┌─────────────────────▼───────────────────────────┐
│ Repository Layer (Trusted)                      │
│ - Parameterized queries                          │
│ - Type checking                                  │
└─────────────────────┬───────────────────────────┘
                      │
                      │
┌─────────────────────▼───────────────────────────┐
│ Database (Trusted)                              │
└─────────────────────────────────────────────────┘
```

---

## Legend

```
│  Vertical connection
─  Horizontal connection
┌  Top-left corner
┐  Top-right corner
└  Bottom-left corner
┘  Bottom-right corner
├  Left T-junction
┤  Right T-junction
┬  Top T-junction
┴  Bottom T-junction
┼  Cross junction
▼  Downward arrow
→  Rightward arrow
```

---

**Document Version:** 1.0.0
**Last Updated:** 2025-12-26
