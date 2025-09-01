# Popular MCP Servers for Thoth Integration

## Overview

This document lists popular MCP (Model Context Protocol) servers that can be integrated with the Thoth agent to extend its capabilities. Each entry includes configuration examples and use cases.

## Official MCP Servers

### 1. GitHub MCP Server
**Purpose**: Access GitHub repositories, issues, pull requests, and code search.

```yaml
- name: github
  url: npx @modelcontextprotocol/server-github
  transport: stdio
  auth:
    type: env
    env_var: GITHUB_TOKEN
  capabilities:
    - code_search
    - issue_management
    - pr_review
    - repository_analysis
```

**Example Usage**:
```
User: "Search for recent issues about MCP integration in the langchain repository"
Agent: "I'll use github.search_issues to find recent MCP-related issues..."
```

### 2. PostgreSQL MCP Server
**Purpose**: Query and manage PostgreSQL databases.

```yaml
- name: postgres
  url: npx @modelcontextprotocol/server-postgres
  transport: stdio
  auth:
    type: env
    env_var: DATABASE_URL
  capabilities:
    - execute_query
    - list_tables
    - describe_schema
    - manage_data
```

**Example Usage**:
```
User: "Show me the schema of the research_papers table"
Agent: "I'll use postgres.describe_table to show you the schema..."
```

### 3. Filesystem MCP Server
**Purpose**: Advanced file system operations beyond basic read/write.

```yaml
- name: filesystem
  url: npx @modelcontextprotocol/server-filesystem
  transport: stdio
  config:
    allowed_directories:
      - /workspace
      - /home/user/documents
  capabilities:
    - file_search
    - bulk_operations
    - watch_changes
    - archive_management
```

### 4. Slack MCP Server
**Purpose**: Interact with Slack workspaces, channels, and messages.

```yaml
- name: slack
  url: npx @modelcontextprotocol/server-slack
  transport: stdio
  auth:
    type: oauth2
    client_id: ${SLACK_CLIENT_ID}
    client_secret: ${SLACK_CLIENT_SECRET}
  capabilities:
    - send_message
    - search_messages
    - manage_channels
    - user_lookup
```

## Community MCP Servers

### 5. Web Browser MCP Server
**Purpose**: Web scraping, browser automation, and interactive browsing.

```yaml
- name: browser
  url: npx @community/mcp-browser-server
  transport: stdio
  config:
    headless: true
    timeout: 30000
  capabilities:
    - navigate
    - scrape
    - screenshot
    - interact_with_page
```

**Example Usage**:
```
User: "Get the latest pricing information from the OpenAI website"
Agent: "I'll use browser.navigate and browser.scrape to get the pricing info..."
```

### 6. Jupyter MCP Server
**Purpose**: Execute code in Jupyter notebooks and manage notebook files.

```yaml
- name: jupyter
  url: npx @community/mcp-jupyter-server
  transport: stdio
  config:
    kernel: python3
    notebook_dir: /workspace/notebooks
  capabilities:
    - execute_code
    - create_notebook
    - manage_cells
    - export_results
```

### 7. Docker MCP Server
**Purpose**: Manage Docker containers, images, and compose stacks.

```yaml
- name: docker
  url: npx @community/mcp-docker-server
  transport: stdio
  auth:
    type: env
    env_var: DOCKER_HOST
  capabilities:
    - list_containers
    - manage_containers
    - build_images
    - compose_operations
```

### 8. AWS MCP Server
**Purpose**: Interact with AWS services (S3, EC2, Lambda, etc.).

```yaml
- name: aws
  url: npx @community/mcp-aws-server
  transport: stdio
  auth:
    type: env
    env_var: AWS_PROFILE
  config:
    region: us-east-1
    services:
      - s3
      - ec2
      - lambda
      - dynamodb
  capabilities:
    - s3_operations
    - ec2_management
    - lambda_invoke
    - resource_query
```

## Research-Specific MCP Servers

### 9. ArXiv MCP Server
**Purpose**: Enhanced ArXiv integration beyond basic search.

```yaml
- name: arxiv-advanced
  url: npx @research/mcp-arxiv-server
  transport: stdio
  capabilities:
    - semantic_search
    - citation_graph
    - author_network
    - trend_analysis
```

### 10. Semantic Scholar MCP Server
**Purpose**: Advanced academic paper search and analysis.

```yaml
- name: semantic-scholar
  url: npx @research/mcp-semantic-scholar
  transport: stdio
  auth:
    type: api_key
    api_key: ${SEMANTIC_SCHOLAR_API_KEY}
  capabilities:
    - paper_search
    - author_search
    - citation_analysis
    - influence_metrics
```

### 11. Zotero MCP Server
**Purpose**: Integrate with Zotero reference management.

```yaml
- name: zotero
  url: npx @research/mcp-zotero-server
  transport: stdio
  auth:
    type: api_key
    api_key: ${ZOTERO_API_KEY}
  config:
    library_type: user
    library_id: ${ZOTERO_LIBRARY_ID}
  capabilities:
    - sync_references
    - manage_collections
    - export_citations
    - attach_files
```

## AI/ML MCP Servers

### 12. Hugging Face MCP Server
**Purpose**: Access Hugging Face models, datasets, and spaces.

```yaml
- name: huggingface
  url: npx @ai/mcp-huggingface-server
  transport: stdio
  auth:
    type: bearer
    token: ${HF_TOKEN}
  capabilities:
    - model_inference
    - dataset_access
    - space_management
    - model_search
```

### 13. OpenAI MCP Server
**Purpose**: Enhanced OpenAI API access with caching and optimization.

```yaml
- name: openai-tools
  url: http://localhost:8090/mcp
  transport: http
  auth:
    type: api_key
    api_key: ${OPENAI_API_KEY}
  capabilities:
    - completion
    - embedding
    - image_generation
    - fine_tuning
```

## Data Analysis MCP Servers

### 14. Pandas MCP Server
**Purpose**: Advanced data manipulation and analysis.

```yaml
- name: pandas
  url: npx @data/mcp-pandas-server
  transport: stdio
  config:
    max_rows: 1000000
    memory_limit: 4GB
  capabilities:
    - load_data
    - transform_data
    - statistical_analysis
    - visualization
```

### 15. SQL MCP Server
**Purpose**: Universal SQL interface for multiple databases.

```yaml
- name: sql-universal
  url: npx @data/mcp-sql-server
  transport: stdio
  config:
    connections:
      - name: research_db
        type: postgresql
        url: ${RESEARCH_DB_URL}
      - name: analytics_db
        type: mysql
        url: ${ANALYTICS_DB_URL}
  capabilities:
    - multi_db_query
    - cross_db_join
    - schema_migration
    - query_optimization
```

## Custom Integration Examples

### 16. Obsidian MCP Server
**Purpose**: Deep integration with Obsidian knowledge base.

```yaml
- name: obsidian
  url: http://localhost:8100/mcp
  transport: http
  config:
    vault_path: /home/user/ObsidianVault
    plugins:
      - dataview
      - templater
  capabilities:
    - note_search
    - graph_analysis
    - template_execution
    - plugin_interaction
```

### 17. Custom Python MCP Server
**Purpose**: Execute custom Python scripts and functions.

```yaml
- name: python-custom
  url: python /workspace/mcp_servers/python_server.py
  transport: stdio
  config:
    modules_path: /workspace/custom_modules
    allowed_imports:
      - numpy
      - pandas
      - scikit-learn
  capabilities:
    - execute_function
    - load_module
    - data_processing
    - ml_inference
```

## Configuration Best Practices

### 1. Security Configuration
```yaml
# Use environment variables for sensitive data
auth:
  type: env
  env_var: ${SERVICE_NAME}_TOKEN

# Restrict permissions
config:
  allowed_operations:
    - read
    - search
  forbidden_paths:
    - /etc
    - /sys
```

### 2. Performance Configuration
```yaml
# Connection pooling
max_connections: 10
connection_timeout: 30
idle_timeout: 300

# Caching
cache:
  enabled: true
  ttl: 3600
  max_size: 100MB
```

### 3. Error Handling Configuration
```yaml
# Retry policy
retry_policy:
  max_attempts: 3
  initial_delay: 1.0
  exponential_base: 2.0
  max_delay: 60.0

# Fallback behavior
fallback:
  enabled: true
  cache_results: true
  notify_user: true
```

## Usage Patterns

### 1. Research Workflow
```python
# Combine multiple servers for research
User: "Find recent papers on transformer architectures and analyze their citations"

# Agent uses:
# 1. arxiv-advanced.semantic_search - Find papers
# 2. semantic-scholar.citation_analysis - Analyze citations
# 3. zotero.sync_references - Save to reference manager
# 4. pandas.statistical_analysis - Generate citation statistics
```

### 2. Development Workflow
```python
# Use development tools together
User: "Create a new Docker container for the MCP server and test it"

# Agent uses:
# 1. filesystem.create_file - Create Dockerfile
# 2. docker.build_image - Build the image
# 3. docker.run_container - Start container
# 4. browser.navigate - Test the endpoint
```

### 3. Data Analysis Workflow
```python
# Complex data analysis across sources
User: "Analyze user engagement data from both PostgreSQL and MySQL databases"

# Agent uses:
# 1. sql-universal.cross_db_query - Query both databases
# 2. pandas.load_data - Load results
# 3. pandas.statistical_analysis - Perform analysis
# 4. slack.send_message - Share results
```

## Adding New MCP Servers

### 1. NPM-based Servers
```bash
# Install globally
npm install -g @organization/mcp-server-name

# Or use npx directly in config
url: npx @organization/mcp-server-name
```

### 2. Docker-based Servers
```yaml
- name: containerized-server
  url: docker run -i mcp-server:latest
  transport: stdio
  config:
    docker_args:
      - --network=host
      - -v /data:/data
```

### 3. Custom HTTP Servers
```yaml
- name: custom-api
  url: https://api.example.com/mcp
  transport: http
  auth:
    type: bearer
    token: ${API_TOKEN}
  headers:
    X-Custom-Header: value
```

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Check network connectivity
   - Verify authentication credentials
   - Ensure server is running

2. **Tool Discovery Issues**
   - Check server capabilities
   - Verify MCP protocol version
   - Review server logs

3. **Performance Problems**
   - Adjust connection pool size
   - Enable caching
   - Check server resource usage

### Debug Configuration
```yaml
- name: debug-server
  url: npx mcp-server --debug
  transport: stdio
  debug:
    log_level: debug
    trace_requests: true
    save_logs: /tmp/mcp-debug.log
```

## Future MCP Servers

### Planned Integrations
1. **Notion MCP Server** - Full Notion workspace access
2. **Kubernetes MCP Server** - K8s cluster management
3. **Elasticsearch MCP Server** - Advanced search capabilities
4. **Redis MCP Server** - Cache and data structure operations
5. **GraphQL MCP Server** - Universal GraphQL endpoint access

### Community Requests
1. **Obsidian Plugin MCP** - Direct plugin API access
2. **Research Gate MCP** - Academic network integration
3. **Mendeley MCP** - Reference manager integration
4. **LaTeX MCP Server** - Document compilation and management
5. **R Studio MCP Server** - Statistical computing integration