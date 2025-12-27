# Browser Workflow Tools - Quick Start Guide

## Overview

8 MCP tools for AI agents to create and manage browser automation workflows.

## Tools Summary

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `create_browser_workflow` | Create new workflow | name, domain, start_url |
| `add_workflow_action` | Add action step | workflow_id, action_type, selector |
| `configure_search` | Setup result extraction | workflow_id, result_selector, title_selector |
| `execute_workflow` | Run workflow | workflow_id, keywords, max_articles |
| `list_workflows` | List all workflows | (none) |
| `get_workflow_details` | Get workflow info | workflow_id |
| `update_workflow_status` | Activate/deactivate | workflow_id, is_active |
| `delete_workflow` | Delete workflow | workflow_id |

## 5-Minute Quick Start

### 1. Create Workflow (30 seconds)
```json
{
  "name": "My First Workflow",
  "website_domain": "example.com",
  "start_url": "https://example.com/search",
  "description": "Test workflow"
}
```
**Returns:** `workflow_id`

### 2. Add Actions (2 minutes)

**Navigate:**
```json
{
  "workflow_id": "<UUID>",
  "action_type": "navigate",
  "value": "https://example.com/search"
}
```

**Type in search:**
```json
{
  "workflow_id": "<UUID>",
  "action_type": "type",
  "selector": "input[name='q']",
  "value": "search query"
}
```

**Click submit:**
```json
{
  "workflow_id": "<UUID>",
  "action_type": "click",
  "selector": "button[type='submit']"
}
```

**Wait for results:**
```json
{
  "workflow_id": "<UUID>",
  "action_type": "wait",
  "selector": ".search-result"
}
```

### 3. Configure Search Extraction (1 minute)
```json
{
  "workflow_id": "<UUID>",
  "result_selector": ".search-result",
  "title_selector": "h2.title",
  "url_selector": "a.link",
  "max_results": 50
}
```

### 4. Execute (30 seconds)
```json
{
  "workflow_id": "<UUID>",
  "keywords": ["keyword1", "keyword2"],
  "max_articles": 30
}
```

### 5. Monitor (30 seconds)
```json
{} // list_workflows takes no parameters
```

## Action Types Reference

| Type | Use Case | Required Fields | Example |
|------|----------|-----------------|---------|
| `navigate` | Go to URL | value (URL) | Navigate to search page |
| `click` | Click element | selector | Click search button |
| `type` | Enter text | selector, value | Type search query |
| `wait` | Wait for element | selector | Wait for results to load |
| `extract` | Extract data | selector | Extract custom fields |
| `scroll` | Scroll page | - | Infinite scroll handling |
| `screenshot` | Capture page | - | Debug or archive |

## Common Patterns

### Pattern: Simple Search Workflow
1. Navigate to search page
2. Type search query
3. Click search button
4. Wait for results
5. Extract results

### Pattern: Multi-Page Discovery
1. Navigate to category page
2. Extract list of article links
3. For each link:
   - Navigate to article
   - Extract metadata
   - Extract content

### Pattern: Infinite Scroll
1. Navigate to page
2. Scroll to bottom
3. Wait for new content
4. Extract results
5. Repeat scroll/wait/extract

## CSS Selector Tips

**Good Selectors (Stable):**
```css
[data-testid="result"]
.search-result
#main-content article
input[name="query"]
```

**Bad Selectors (Fragile):**
```css
div > div > div:nth-child(3)
.col-md-6
body > div
```

**Relative Selectors (Within Results):**
```css
/* Result container */
.search-result

/* Title within result */
h2.title

/* URL within result */
a.article-link
```

## Error Handling

All errors return:
```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "✗ Error description"
  }]
}
```

**Common Errors:**
- Workflow not found → Check workflow_id
- No actions defined → Add actions first
- Invalid selector → Test in DevTools
- Workflow inactive → Activate workflow

## Best Practices

### ✓ DO:
- Use descriptive workflow names
- Test selectors in browser first
- Add explicit waits after actions
- Set reasonable max_results
- Monitor execution statistics
- Deactivate broken workflows

### ✗ DON'T:
- Use fragile CSS selectors
- Skip wait steps
- Set excessive max_results
- Leave failed workflows active
- Hardcode dynamic content

## Integration Points

**With Research Queries:**
```
query.keywords → workflow.execute(keywords)
```

**With Discovery Sources:**
```
workflow.results → discovery_source.articles
```

**With Article Processing:**
```
workflow.extract → processing_service.process_pdf
```

## Database Tables

- `browser_workflows` - Main workflow config
- `workflow_actions` - Action steps
- `workflow_search_config` - Extraction rules
- `workflow_executions` - Execution history

## Workflow Lifecycle

```
Create → Add Actions → Configure Search → Execute → Monitor
  ↓                                                      ↓
Activate ←─────────────────────────────────────────────┘
  ↓
Deactivate (if needed)
  ↓
Delete (if obsolete)
```

## Quick Debugging

**Workflow not executing?**
1. Check if active: `get_workflow_details`
2. Verify actions exist: Look at action count
3. Check search config: Verify selectors
4. Review last error: Check execution history

**No results extracted?**
1. Test selectors in DevTools
2. Verify result_selector matches containers
3. Check if page structure changed
4. Add wait steps if needed

**Slow execution?**
1. Reduce max_results
2. Optimize wait timeouts
3. Remove unnecessary actions
4. Check network latency

## Tool Chaining Examples

**Create Complete Workflow:**
```
1. create_browser_workflow
2. add_workflow_action (4x for 4 steps)
3. configure_search
4. execute_workflow
5. list_workflows (verify)
```

**Update Existing Workflow:**
```
1. get_workflow_details (review current)
2. add_workflow_action (add new step)
3. configure_search (update selectors)
4. execute_workflow (test)
```

**Workflow Maintenance:**
```
1. list_workflows (find failing)
2. get_workflow_details (diagnose)
3. update_workflow_status (deactivate)
4. delete_workflow (if obsolete)
```

## Performance Tips

- **Batch actions** - Add all actions before executing
- **Cache selectors** - Reuse working selector patterns
- **Limit results** - Set reasonable max_results
- **Monitor health** - Check execution statistics
- **Clean up** - Delete unused workflows

## Next Steps

1. **Read full documentation:** `BROWSER_WORKFLOW_TOOLS.md`
2. **Check examples:** See complete workflow examples
3. **Test in production:** Start with simple workflows
4. **Monitor metrics:** Track success rates
5. **Optimize:** Refine selectors and actions

## Support

- **Logs:** Check application logs for detailed errors
- **DevTools:** Use browser DevTools to test selectors
- **Statistics:** Review workflow execution metrics
- **Documentation:** Full docs in `BROWSER_WORKFLOW_TOOLS.md`

---

**Ready to start?** Create your first workflow in 5 minutes! 🚀
