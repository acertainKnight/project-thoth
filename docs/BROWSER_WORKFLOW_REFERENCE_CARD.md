# Browser Workflow MCP Tools - Quick Reference Card

## 8 Tools at a Glance

| # | Tool Name | Purpose | Key Parameters | Returns |
|---|-----------|---------|----------------|---------|
| 1 | `create_browser_workflow` | Create workflow | name, domain, start_url | workflow_id |
| 2 | `add_workflow_action` | Add action step | workflow_id, action_type, selector | action_id |
| 3 | `configure_search` | Setup extraction | workflow_id, selectors | config_id |
| 4 | `execute_workflow` | Run workflow | workflow_id, keywords | results |
| 5 | `list_workflows` | List all | (none) | workflow list |
| 6 | `get_workflow_details` | Get details | workflow_id | full details |
| 7 | `update_workflow_status` | Enable/disable | workflow_id, is_active | success |
| 8 | `delete_workflow` | Delete | workflow_id | success |

## Action Types

| Type | Use Case | Required Fields |
|------|----------|-----------------|
| `navigate` | Go to URL | value (URL) |
| `click` | Click element | selector |
| `type` | Enter text | selector, value |
| `wait` | Wait for element | selector |
| `extract` | Extract data | selector |
| `scroll` | Scroll page | (optional config) |
| `screenshot` | Capture image | (optional path) |

## Workflow Creation Sequence

```
1. create_browser_workflow
   ↓
2. add_workflow_action (multiple)
   ↓
3. configure_search
   ↓
4. execute_workflow
```

## Example: Complete Workflow

```json
// 1. Create
{
  "tool": "create_browser_workflow",
  "args": {
    "name": "ArXiv ML Papers",
    "website_domain": "arxiv.org",
    "start_url": "https://arxiv.org/search"
  }
}

// 2. Add Actions
{
  "tool": "add_workflow_action",
  "args": {
    "workflow_id": "<UUID>",
    "action_type": "navigate",
    "value": "https://arxiv.org/search"
  }
}

{
  "tool": "add_workflow_action",
  "args": {
    "workflow_id": "<UUID>",
    "action_type": "type",
    "selector": "input[name='query']",
    "value": "machine learning"
  }
}

{
  "tool": "add_workflow_action",
  "args": {
    "workflow_id": "<UUID>",
    "action_type": "click",
    "selector": "button[type='submit']"
  }
}

// 3. Configure
{
  "tool": "configure_search",
  "args": {
    "workflow_id": "<UUID>",
    "result_selector": ".arxiv-result",
    "title_selector": ".title",
    "url_selector": "a.list-title"
  }
}

// 4. Execute
{
  "tool": "execute_workflow",
  "args": {
    "workflow_id": "<UUID>",
    "keywords": ["neural networks"]
  }
}
```

## CSS Selector Patterns

### Good (Stable)
```css
[data-testid="result"]
.search-result
#main-content article
input[name="query"]
```

### Bad (Fragile)
```css
div > div:nth-child(3)
.col-md-6
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Workflow not found | Invalid ID | Check workflow_id |
| No actions defined | Empty actions | Add actions first |
| Invalid selector | Bad CSS | Test in DevTools |
| Workflow inactive | Disabled | Activate workflow |

## Response Format

### Success
```json
{
  "content": [{
    "type": "text",
    "text": "✓ Success message..."
  }],
  "isError": false
}
```

### Error
```json
{
  "content": [{
    "type": "text",
    "text": "✗ Error message..."
  }],
  "isError": true
}
```

## Status Codes

- **Active** - Workflow enabled and ready
- **Inactive** - Workflow disabled
- **Degraded** - Some executions failing
- **Down** - Consistently failing
- **Unknown** - Not yet executed

## Repository Classes

- `BrowserWorkflowRepository` - Main workflow CRUD
- `WorkflowActionsRepository` - Action management
- `WorkflowSearchConfigRepository` - Search config
- `WorkflowExecutionsRepository` - History tracking

## Database Tables

- `browser_workflows` - Main config
- `workflow_actions` - Action steps
- `workflow_search_config` - Extraction rules
- `workflow_executions` - History

## Performance Tips

✓ **DO:**
- Use specific CSS selectors
- Add explicit waits
- Set reasonable max_results
- Monitor statistics
- Clean up old workflows

✗ **DON'T:**
- Use fragile selectors
- Skip wait steps
- Set excessive limits
- Leave failed workflows active

## Documentation

- **Quick Start:** `BROWSER_WORKFLOW_QUICK_START.md`
- **Full API:** `BROWSER_WORKFLOW_TOOLS.md`
- **Technical:** `BROWSER_WORKFLOW_IMPLEMENTATION.md`
- **Architecture:** `BROWSER_WORKFLOW_ARCHITECTURE.md`
- **Summary:** `BROWSER_WORKFLOW_SUMMARY.md`

## Tool Locations

```
Implementation:
  src/thoth/mcp/tools/browser_workflow_tools.py

Registration:
  src/thoth/mcp/tools/__init__.py

Documentation:
  docs/BROWSER_WORKFLOW_*.md
```

## Version Info

- **Version:** 1.0.0
- **Created:** 2025-12-26
- **Tools:** 8
- **Status:** Production-ready
- **Dependencies:** PostgreSQL, MCP Server

---

**Print this for quick reference!** 📋
