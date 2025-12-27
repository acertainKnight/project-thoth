# Browser Workflow MCP Tools

Complete guide for AI agents to create and manage browser-based discovery workflows.

## Overview

Browser workflow tools enable AI agents to:
- Create automated browser workflows for article discovery
- Configure action sequences (navigate, click, type, extract)
- Set up search result extraction with CSS selectors
- Execute workflows and monitor results
- Manage workflow lifecycle (activate, deactivate, delete)

## Architecture

The browser workflow system consists of four main components:

1. **Browser Workflows** - Main workflow configuration
2. **Workflow Actions** - Sequential action steps
3. **Workflow Search Config** - Search result extraction rules
4. **Workflow Executions** - Execution history and metrics

## Available Tools

### 1. create_browser_workflow

Create a new browser workflow for automated discovery.

**Parameters:**
- `name` (string, required) - Unique workflow name
- `website_domain` (string, required) - Target domain (e.g., "arxiv.org")
- `start_url` (string, required) - Starting URL for workflow
- `description` (string, required) - Workflow description
- `extraction_rules` (object, optional) - JSON rules for data extraction
- `is_active` (boolean, optional) - Active status (default: true)

**Returns:** Workflow ID (UUID)

**Example:**
```json
{
  "name": "ArXiv ML Papers",
  "website_domain": "arxiv.org",
  "start_url": "https://arxiv.org/search",
  "description": "Automated discovery of machine learning papers from ArXiv",
  "is_active": true
}
```

**Response:**
```
✓ Browser workflow created successfully!

**Workflow ID:** 550e8400-e29b-41d4-a716-446655440000
**Name:** ArXiv ML Papers
**Domain:** arxiv.org
**Start URL:** https://arxiv.org/search
**Status:** Active

Next steps:
1. Add actions with `add_workflow_action`
2. Configure search with `configure_search`
3. Execute with `execute_workflow`
```

---

### 2. add_workflow_action

Add an action step to a workflow. Actions define browser automation steps.

**Parameters:**
- `workflow_id` (string, required) - Workflow UUID
- `action_type` (string, required) - Action type:
  - `navigate` - Navigate to URL
  - `click` - Click element
  - `type` - Type text into input
  - `extract` - Extract data from page
  - `wait` - Wait for element/timeout
  - `scroll` - Scroll page
  - `screenshot` - Take screenshot
- `selector` (string, optional) - CSS selector for target element
- `value` (string, optional) - Value to use (URL, text, etc.)
- `step_number` (integer, optional) - Position in sequence (auto-increments)
- `action_config` (object, optional) - Additional configuration

**Returns:** Action ID (UUID)

**Example - Navigate:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "action_type": "navigate",
  "value": "https://arxiv.org/search"
}
```

**Example - Type in Search:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "action_type": "type",
  "selector": "input[name='query']",
  "value": "machine learning",
  "step_number": 2
}
```

**Example - Click Button:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "action_type": "click",
  "selector": "button[type='submit']",
  "step_number": 3
}
```

**Example - Wait for Results:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "action_type": "wait",
  "selector": ".search-result",
  "action_config": {
    "timeout": 5000,
    "waitFor": "visible"
  },
  "step_number": 4
}
```

**Response:**
```
✓ Workflow action added successfully!

**Action ID:** 660e8400-e29b-41d4-a716-446655440001
**Workflow ID:** 550e8400-e29b-41d4-a716-446655440000
**Step:** 2
**Type:** type
**Selector:** input[name='query']
**Value:** machine learning
```

---

### 3. configure_search

Configure how to extract search results from the page.

**Parameters:**
- `workflow_id` (string, required) - Workflow UUID
- `result_selector` (string, required) - CSS selector for result containers
- `title_selector` (string, required) - CSS selector for titles (relative to result)
- `url_selector` (string, required) - CSS selector for URLs (relative to result)
- `snippet_selector` (string, optional) - CSS selector for snippets
- `search_input_selector` (string, optional) - CSS selector for search input
- `search_button_selector` (string, optional) - CSS selector for search button
- `max_results` (integer, optional) - Maximum results to extract (default: 100)
- `pagination_config` (object, optional) - Pagination configuration

**Returns:** Config ID (UUID)

**Example:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "result_selector": ".arxiv-result",
  "title_selector": ".title",
  "url_selector": ".list-title a",
  "snippet_selector": ".abstract-short",
  "max_results": 50
}
```

**Response:**
```
✓ Search configuration created successfully!

**Config ID:** 770e8400-e29b-41d4-a716-446655440002
**Workflow ID:** 550e8400-e29b-41d4-a716-446655440000
**Result Selector:** .arxiv-result
**Title Selector:** .title
**URL Selector:** .list-title a
**Max Results:** 50
**Snippet Selector:** .abstract-short
```

---

### 4. execute_workflow

Execute a browser workflow to discover and extract articles.

**Parameters:**
- `workflow_id` (string, required) - Workflow UUID
- `keywords` (array of strings, optional) - Search keywords
- `date_range` (object, optional) - Date range filter
  - `start` (string) - Start date (YYYY-MM-DD)
  - `end` (string) - End date (YYYY-MM-DD)
- `max_articles` (integer, optional) - Maximum articles (default: 50)

**Returns:** Execution results with article count

**Example:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "keywords": ["machine learning", "neural networks"],
  "max_articles": 30
}
```

**Response:**
```
✓ Workflow execution initiated!

**Workflow:** ArXiv ML Papers
**Domain:** arxiv.org
**Actions:** 4 steps
**Search Config:** Configured

⚠️ Note: Full browser automation requires Playwright integration.
This is a placeholder response. Actual execution would:
1. Launch browser session
2. Execute 4 action steps
3. Extract articles using search config
4. Store results in database

**Execution Parameters:**
- Keywords: ['machine learning', 'neural networks']
- Max Articles: 30

**Duration:** 145ms
**Articles Found:** 0
```

---

### 5. list_workflows

List all browser workflows with statistics.

**Parameters:** None (no input required)

**Returns:** List of workflows with execution statistics

**Example:**
```json
{}
```

**Response:**
```
**Browser Workflows Summary**

Total Workflows: 3
Active: 2
Healthy: 2
Total Executions: 47
Success Rate: 95.7%
Total Articles: 1,234

---

**Individual Workflows:**

**ArXiv ML Papers**
  - ID: 550e8400-e29b-41d4-a716-446655440000
  - Domain: arxiv.org
  - Health: active
  - Executions: 25
  - Success Rate: 96.0%
  - Articles Extracted: 780
  - Avg Duration: 3450ms
  - Last Run: 2025-12-26 10:30:00

**PubMed Clinical Trials**
  - ID: 660e8400-e29b-41d4-a716-446655440001
  - Domain: pubmed.ncbi.nlm.nih.gov
  - Health: active
  - Executions: 18
  - Success Rate: 94.4%
  - Articles Extracted: 342
  - Avg Duration: 2890ms
  - Last Run: 2025-12-26 09:15:00
```

---

### 6. get_workflow_details

Get detailed information about a specific workflow.

**Parameters:**
- `workflow_id` (string, required) - Workflow UUID

**Returns:** Detailed workflow information including actions and config

**Example:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```
**Workflow Details: ArXiv ML Papers**

**Basic Information:**
- ID: 550e8400-e29b-41d4-a716-446655440000
- Domain: arxiv.org
- Start URL: https://arxiv.org/search
- Description: Automated discovery of machine learning papers from ArXiv
- Status: Active
- Health: active

**Statistics:**
- Total Executions: 25
- Successful: 24
- Failed: 1
- Success Rate: 96.0%
- Articles Extracted: 780
- Avg Duration: 3450ms
- Last Executed: 2025-12-26 10:30:00
- Last Success: 2025-12-26 10:30:00

**Actions (4 steps):**
  Step 1: navigate
    - Value: https://arxiv.org/search
  Step 2: type
    - Selector: input[name='query']
    - Value: machine learning
  Step 3: click
    - Selector: button[type='submit']
  Step 4: wait
    - Selector: .search-result

**Search Configuration:**
- Result Selector: .arxiv-result
- Title Selector: .title
- URL Selector: .list-title a
- Snippet Selector: .abstract-short
- Max Results: 50
```

---

### 7. update_workflow_status

Activate or deactivate a workflow.

**Parameters:**
- `workflow_id` (string, required) - Workflow UUID
- `is_active` (boolean, required) - Active status

**Returns:** Success confirmation

**Example - Deactivate:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_active": false
}
```

**Response:**
```
✓ Workflow deactivated successfully!
```

---

### 8. delete_workflow

Delete a workflow and all associated data.

**Parameters:**
- `workflow_id` (string, required) - Workflow UUID

**Returns:** Deletion confirmation

**Example:**
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```
✓ Workflow "ArXiv ML Papers" deleted successfully!
```

---

## Complete Workflow Example

Here's a complete example of creating and executing a workflow:

### Step 1: Create Workflow
```json
{
  "tool": "create_browser_workflow",
  "arguments": {
    "name": "Nature Articles Discovery",
    "website_domain": "nature.com",
    "start_url": "https://www.nature.com/search",
    "description": "Discover latest Nature journal articles"
  }
}
```

### Step 2: Add Navigation Action
```json
{
  "tool": "add_workflow_action",
  "arguments": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_type": "navigate",
    "value": "https://www.nature.com/search"
  }
}
```

### Step 3: Add Search Input Action
```json
{
  "tool": "add_workflow_action",
  "arguments": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_type": "type",
    "selector": "input[name='q']",
    "value": "climate change"
  }
}
```

### Step 4: Add Search Button Click
```json
{
  "tool": "add_workflow_action",
  "arguments": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_type": "click",
    "selector": "button[type='submit']"
  }
}
```

### Step 5: Add Wait for Results
```json
{
  "tool": "add_workflow_action",
  "arguments": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_type": "wait",
    "selector": "article.search-result",
    "action_config": {
      "timeout": 5000
    }
  }
}
```

### Step 6: Configure Search Extraction
```json
{
  "tool": "configure_search",
  "arguments": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "result_selector": "article.search-result",
    "title_selector": "h3.title a",
    "url_selector": "h3.title a",
    "snippet_selector": ".description",
    "max_results": 50
  }
}
```

### Step 7: Execute Workflow
```json
{
  "tool": "execute_workflow",
  "arguments": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "keywords": ["climate change", "biodiversity"],
    "max_articles": 30
  }
}
```

---

## Best Practices

### 1. CSS Selectors
- Use specific, stable selectors (prefer IDs and data attributes)
- Avoid fragile selectors (nth-child, absolute positioning)
- Test selectors in browser DevTools first
- Use relative selectors within result containers

**Good:**
```css
article[data-testid="search-result"]
.search-result h3.article-title
```

**Bad:**
```css
div > div > div:nth-child(3)
.container > div
```

### 2. Action Sequences
- Start with navigation
- Add waits after actions that trigger page changes
- Use explicit waits over fixed timeouts
- Include error handling in action_config

### 3. Search Configuration
- Test extraction on actual page first
- Use relative selectors within result containers
- Handle missing optional fields gracefully
- Set reasonable max_results limits

### 4. Workflow Management
- Use descriptive workflow names
- Document extraction rules
- Monitor execution statistics
- Deactivate failing workflows
- Clean up unused workflows

---

## Error Handling

All tools return structured error responses:

```json
{
  "isError": true,
  "content": [{
    "type": "text",
    "text": "✗ Error message with details"
  }]
}
```

Common errors:
- **Workflow not found** - Invalid workflow_id
- **No actions defined** - Add actions before execution
- **Invalid selector** - Check CSS selector syntax
- **Workflow inactive** - Activate workflow first

---

## Integration with Other Tools

Browser workflows integrate with:

- **Research Queries** - Use query criteria for workflow filtering
- **Discovery Sources** - Complement API-based discovery
- **Article Processing** - Extract and process discovered articles
- **Tag Management** - Auto-tag discovered articles

---

## Database Schema

### browser_workflows
```sql
- id (UUID, primary key)
- name (VARCHAR, unique)
- website_domain (VARCHAR)
- start_url (TEXT)
- description (TEXT)
- extraction_rules (JSONB)
- is_active (BOOLEAN)
- health_status (VARCHAR)
- total_executions (INTEGER)
- successful_executions (INTEGER)
- failed_executions (INTEGER)
- total_articles_extracted (INTEGER)
- average_execution_time_ms (INTEGER)
- last_executed_at (TIMESTAMP)
- last_success_at (TIMESTAMP)
- last_failure_at (TIMESTAMP)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

### workflow_actions
```sql
- id (UUID, primary key)
- workflow_id (UUID, foreign key)
- step_number (INTEGER)
- action_type (VARCHAR)
- selector (TEXT)
- value (TEXT)
- action_config (JSONB)
- created_at (TIMESTAMP)
```

### workflow_search_config
```sql
- id (UUID, primary key)
- workflow_id (UUID, foreign key, unique)
- result_selector (TEXT)
- title_selector (TEXT)
- url_selector (TEXT)
- snippet_selector (TEXT)
- max_results (INTEGER)
- pagination_config (JSONB)
- created_at (TIMESTAMP)
```

---

## Future Enhancements

Planned features:
- [ ] Playwright/Selenium integration for actual browser automation
- [ ] Screenshot capture and storage
- [ ] Advanced pagination support
- [ ] JavaScript execution support
- [ ] Cookie and session management
- [ ] Proxy and user-agent rotation
- [ ] Rate limiting and politeness delays
- [ ] Headless vs headful browser modes
- [ ] Browser profile management
- [ ] Network request interception
- [ ] Form handling with complex inputs
- [ ] Multi-page navigation workflows
- [ ] Conditional logic in action sequences
- [ ] Workflow templates and cloning
- [ ] Real-time execution monitoring
- [ ] Workflow scheduling and automation

---

## Support

For issues or questions:
- Check workflow execution logs
- Verify CSS selectors on target website
- Test actions manually in browser
- Review workflow statistics for patterns
- Contact development team for assistance
