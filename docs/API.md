# Thoth API Documentation

This document provides comprehensive documentation for the Thoth Research Assistant API, including REST endpoints, WebSocket connections, and MCP protocol integration.

## Base Information

- **Base URL**: `http://localhost:8000` (default)
- **Content Type**: `application/json`
- **Authentication**: Not required for local usage
- **API Type**: FastAPI with automatic OpenAPI documentation

## REST API Endpoints

### Chat Operations

#### Create Chat Session
```http
POST /chat/sessions
Content-Type: application/json

{
  "title": "Research Session Title",
  "metadata": {
    "topic": "machine learning"
  }
}
```

**Response:**
```json
{
  "id": "session-uuid",
  "title": "Research Session Title",
  "created_at": "2024-01-15T10:30:00Z",
  "is_active": true,
  "metadata": {
    "topic": "machine learning"
  }
}
```

#### List Chat Sessions
```http
GET /chat/sessions?active_only=true&limit=50
```

**Query Parameters:**
- `active_only` (bool): Return only active sessions (default: true)
- `limit` (int): Maximum number of sessions to return (default: 50)

#### Research Chat
```http
POST /research/chat
Content-Type: application/json

{
  "message": "What are the latest developments in transformer architectures?",
  "session_id": "optional-session-id",
  "conversation_id": "optional-conversation-id"
}
```

**Response:**
```json
{
  "id": "message-uuid",
  "session_id": "session-uuid",
  "role": "assistant",
  "content": "Based on recent research papers in your collection...",
  "timestamp": "2024-01-15T10:31:00Z",
  "metadata": {
    "model_used": "anthropic/claude-3-sonnet",
    "tokens_used": 234,
    "processing_time": 2.3,
    "sources_referenced": ["paper-1", "paper-2"]
  }
}
```

#### Get Chat History
```http
GET /chat/sessions/{session_id}/messages?limit=100&offset=0
```

**Query Parameters:**
- `limit` (int): Maximum messages to return (default: 100)
- `offset` (int): Number of messages to skip (default: 0)

#### Search Chat Messages
```http
GET /chat/search?query=attention%20mechanisms&limit=50
```

**Query Parameters:**
- `query` (string): Search query for message content
- `session_id` (string, optional): Limit search to specific session
- `limit` (int): Maximum results (default: 50)

### System Operations

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "llm_service": {"status": "healthy"},
    "discovery_service": {"status": "healthy"},
    "rag_service": {"status": "healthy"}
  }
}
```

#### Download PDF
```http
GET /download-pdf?url=https://arxiv.org/pdf/1706.03762.pdf
```

**Query Parameters:**
- `url` (string): URL of the PDF to download

#### View Markdown
```http
GET /view-markdown?path=/path/to/markdown/file.md
```

**Query Parameters:**
- `path` (string): Path to the markdown file to view

### Agent Operations

#### Agent Status
```http
GET /agent/status
```

**Response:**
```json
{
  "status": "running",
  "agent_type": "research_assistant",
  "tools_available": 15,
  "memory_enabled": true
}
```

#### List Agent Tools
```http
GET /agent/tools
```

#### Agent Configuration
```http
GET /agent/config
```

```http
POST /agent/config
Content-Type: application/json

{
  "model": "anthropic/claude-3-sonnet",
  "temperature": 0.7,
  "max_tokens": 4000
}
```

#### Restart Agent
```http
POST /agent/restart
```

#### Get Document Status
```http
GET /api/v1/documents/{document_id}/status
```

**Response:**
```json
{
  "document_id": "doc-uuid",
  "status": "processing",  // "uploaded", "processing", "completed", "failed"
  "progress": 0.75,
  "current_stage": "citation_extraction",
  "estimated_completion": "2024-01-15T10:35:00Z",
  "error_message": null
}
```

#### Get Document Content
```http
GET /api/v1/documents/{document_id}/content
```

**Query Parameters:**
- `include_metadata` (bool): Include document metadata
- `include_citations` (bool): Include extracted citations
- `format` (string): Response format ("json", "markdown", "text")

#### Search Documents
```http
GET /api/v1/documents/search
```

**Query Parameters:**
- `q` (string): Search query
- `limit` (int): Maximum results
- `offset` (int): Pagination offset
- `tags` (string): Comma-separated tags to filter by
- `date_from` (string): ISO date for filtering
- `date_to` (string): ISO date for filtering

### Research Operations

#### Research Query
```http
POST /research/query
Content-Type: application/json

{
  "query": "Find papers related to attention mechanisms",
  "max_results": 20,
  "include_metadata": true
}
```

**Response:**
```json
{
  "query": "Find papers related to attention mechanisms",
  "results": "Research findings about attention mechanisms...",
  "response": "Detailed analysis of attention mechanisms in current literature..."
}
```

### Batch and Command Operations

#### Execute Command
```http
POST /execute/command
Content-Type: application/json

{
  "command": "discovery",
  "subcommand": "list",
  "options": {},
  "stream_output": false
}
```

#### Batch Process
```http
POST /batch/process
Content-Type: application/json

{
  "items": [
    {"path": "/path/to/paper1.pdf"},
    {"path": "/path/to/paper2.pdf"}
  ],
  "operation_type": "process",
  "max_concurrent": 3
}
```

#### Execute Tool Directly
```http
POST /tools/execute
Content-Type: application/json

{
  "tool_name": "search_knowledge_base",
  "parameters": {
    "query": "attention mechanisms",
    "max_results": 10
  },
  "bypass_agent": false
}
```

### Configuration Management

#### Export Configuration
```http
GET /config/export
```

#### Import Configuration
```http
POST /config/import
Content-Type: application/json

{
  "obsidian_config": {
    "workspace_directory": "/path/to/workspace",
    "api_keys": {...}
  }
}
```

#### Validate Configuration
```http
POST /config/validate
```

#### Get Configuration Schema
```http
GET /config/schema
```

## WebSocket API

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### Message Format
All WebSocket messages follow this format:
```json
{
  "type": "message_type",
  "id": "unique-message-id",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    // Message-specific data
  }
}
```

### Chat WebSocket
```javascript
// Connect to chat WebSocket
const chatWs = new WebSocket('ws://localhost:8000/ws/chat');

// Send message
chatWs.send(JSON.stringify({
  "type": "chat_message",
  "data": {
    "message": "What are the key findings in transformer research?",
    "model": "anthropic/claude-3-sonnet"
  }
}));

// Receive response
chatWs.onmessage = (event) => {
  const response = JSON.parse(event.data);
  if (response.type === "chat_response") {
    console.log("AI Response:", response.data.content);
  }
};
```

### Status Updates WebSocket
```javascript
// Connect to status updates
const statusWs = new WebSocket('ws://localhost:8000/ws/status');
```

### Progress Updates WebSocket
```javascript
// Connect to progress updates
const progressWs = new WebSocket('ws://localhost:8000/ws/progress');

processingWs.onmessage = (event) => {
  const update = JSON.parse(event.data);
  switch (update.type) {
    case "document_processing":
      console.log(`Document ${update.data.document_id}: ${update.data.status} (${update.data.progress}%)`);
      break;
    case "discovery_update":
      console.log(`Discovery: Found ${update.data.found_count} papers for "${update.data.query}"`);
      break;
  }
};
```

### System Notifications
```javascript
const notificationWs = new WebSocket('ws://localhost:8000/ws/notifications');

notificationWs.onmessage = (event) => {
  const notification = JSON.parse(event.data);
  console.log(`System ${notification.data.level}: ${notification.data.message}`);
};
```

## MCP Protocol Integration

Thoth implements the Model Context Protocol for AI agent integration.

### MCP Server Endpoints

#### Initialize Connection
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "roots": {
        "listChanged": true
      }
    },
    "clientInfo": {
      "name": "Claude",
      "version": "1.0"
    }
  }
}
```

#### List Available Tools
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "thoth_search_papers",
        "description": "Search for research papers in the knowledge base",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "Search query for papers"
            },
            "limit": {
              "type": "number",
              "description": "Maximum number of results"
            }
          },
          "required": ["query"]
        }
      }
    ]
  }
}
```

### Available MCP Tools

#### Advanced RAG Tools

**reindex_collection**
Rebuild the entire RAG index from scratch.

**Parameters:**
- `clear_existing` (boolean): Clear existing index before rebuilding
- `include_notes` (boolean): Include note files in reindexing
- `include_articles` (boolean): Include article files in reindexing
- `batch_size` (integer): Documents per batch (10-1000)

**semantic_search**
Perform advanced semantic search with filtering.

**Parameters:**
- `query` (string): Search query
- `collection_name` (string): Target collection
- `top_k` (integer): Number of results
- `filter_metadata` (object): Metadata filters

#### Analysis Tools

**analyze_paper_connections**
Analyze relationships between papers in the knowledge base.

**Parameters:**
- `paper_ids` (array): List of paper IDs to analyze
- `analysis_depth` (integer): Depth of relationship analysis
- `include_citations` (boolean): Include citation relationships

**evaluate_research_topic**
Comprehensive evaluation of a research topic across the corpus.

**Parameters:**
- `topic` (string): Research topic
- `time_range` (object): Date range for analysis
- `include_trends` (boolean): Include trend analysis

#### Discovery Tools

**manage_discovery_sources**
Create, update, or manage discovery sources.

**Parameters:**
- `action` (string): "create", "update", "delete", "list"
- `source_config` (object): Source configuration
- `source_id` (string): Source identifier (for update/delete)

**schedule_discovery_task**
Schedule automated discovery tasks.

**Parameters:**
- `source_ids` (array): Discovery sources to run
- `schedule_type` (string): "once", "interval", "cron"
- `schedule_config` (object): Schedule configuration

#### Citation Tools

**extract_citation_network**
Extract and analyze citation networks from documents.

**Parameters:**
- `document_ids` (array): Documents to analyze
- `include_external` (boolean): Include external citations
- `max_depth` (integer): Citation network depth

**validate_citations**
Validate and enrich citation metadata.

**Parameters:**
- `citation_list` (array): Citations to validate
- `auto_correct` (boolean): Automatically correct errors
- `fetch_metadata` (boolean): Fetch additional metadata

#### Processing Tools

**process_document_batch**
Process multiple documents with advanced options.

**Parameters:**
- `document_paths` (array): Paths to documents
- `processing_options` (object): Processing configuration
- `priority` (string): Processing priority
- `notify_completion` (boolean): Send completion notifications

**monitor_processing_queue**
Monitor and manage document processing queue.

**Parameters:**
- `queue_name` (string): Processing queue identifier
- `action` (string): "status", "pause", "resume", "clear"

#### Query Management Tools

**manage_research_queries**
Create and manage research queries for filtering and evaluation.

**Parameters:**
- `action` (string): "create", "update", "delete", "list", "evaluate"
- `query_config` (object): Query configuration
- `query_id` (string): Query identifier

**evaluate_query_performance**
Evaluate how well queries perform in finding relevant papers.

**Parameters:**
- `query_ids` (array): Queries to evaluate
- `test_corpus` (array): Test document set
- `metrics` (array): Evaluation metrics to compute

#### Data Management Tools

**export_research_data**
Export research data in various formats.

**Parameters:**
- `export_type` (string): "papers", "citations", "knowledge_graph", "all"
- `format` (string): "json", "csv", "bibtex", "graphml"
- `filter_criteria` (object): Export filters

**backup_knowledge_base**
Create backups of the knowledge base and associated data.

**Parameters:**
- `backup_type` (string): "full", "incremental", "metadata_only"
- `compression` (boolean): Compress backup files
- `include_vectors` (boolean): Include vector embeddings

## Client SDKs

### Python SDK

```python
from thoth_client import ThothClient

# Initialize client
client = ThothClient(base_url="http://localhost:8000", api_key="optional")

# Chat operations
session = client.chat.create_session(title="Research Session")
response = client.chat.send_message(session.id, "What are the latest ML papers?")

# Document operations
doc = client.documents.upload("paper.pdf")
client.documents.process(doc.document_id, extract_citations=True)

# Search operations
results = client.search.papers("transformer attention", limit=10)
rag_response = client.rag.generate("Explain attention mechanisms", max_tokens=1000)

# Discovery operations
task = client.discovery.start("quantum computing", sources=["arxiv"])
results = client.discovery.get_results(task.task_id)
```

### JavaScript SDK

```javascript
import { ThothClient } from 'thoth-js-client';

const client = new ThothClient({
  baseURL: 'http://localhost:8000',
  apiKey: 'optional'
});

// Chat operations
const session = await client.chat.createSession({ title: 'Research Session' });
const response = await client.chat.sendMessage(session.id, 'What are recent AI developments?');

// Document operations
const doc = await client.documents.upload(file);
await client.documents.process(doc.document_id, { extractCitations: true });

// Search and RAG
const papers = await client.search.papers('machine learning', { limit: 10 });
const ragResponse = await client.rag.generate('Explain neural networks');
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "The 'query' parameter is required",
    "details": {
      "parameter": "query",
      "provided_value": null,
      "expected_type": "string"
    },
    "request_id": "req-uuid",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes

- `INVALID_PARAMETER`: Missing or invalid request parameter
- `DOCUMENT_NOT_FOUND`: Requested document doesn't exist
- `PROCESSING_FAILED`: Document processing failed
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `SERVICE_UNAVAILABLE`: External service unavailable
- `INSUFFICIENT_STORAGE`: Not enough disk space
- `MODEL_ERROR`: LLM provider error

## Rate Limiting

### Default Limits
- **Chat API**: 100 requests per minute per IP
- **Document Upload**: 10 files per minute per IP
- **Search API**: 200 requests per minute per IP
- **Discovery API**: 5 concurrent tasks per IP

### Rate Limit Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
X-RateLimit-Window: 60
```

## Authentication

### API Key Authentication
```http
GET /api/v1/documents
Authorization: Bearer your-api-key-here
```

Or via header:
```http
GET /api/v1/documents
X-API-Key: your-api-key-here
```

### WebSocket Authentication
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat', [], {
  headers: {
    'Authorization': 'Bearer your-api-key-here'
  }
});
```

## Development and Testing

### API Testing

#### Using curl
```bash
# Health check
curl http://localhost:8000/api/v1/system/health

# Create chat session
curl -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}'

# Send message
curl -X POST http://localhost:8000/api/v1/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Thoth!"}'
```

#### Using Python requests
```python
import requests

# Health check
response = requests.get("http://localhost:8000/api/v1/system/health")
print(response.json())

# Create chat session
session_data = {"title": "Test Session"}
session_response = requests.post("http://localhost:8000/api/v1/chat/sessions",
                                json=session_data)
session_id = session_response.json()["id"]

# Send message
message_data = {"message": "What can you help me with?"}
message_response = requests.post(f"http://localhost:8000/api/v1/chat/sessions/{session_id}/messages",
                                json=message_data)
print(message_response.json()["content"])
```

### OpenAPI Specification

The complete OpenAPI specification is available at:
```
GET /api/v1/openapi.json
```

Interactive API documentation:
```
GET /docs  # Swagger UI
GET /redoc  # ReDoc
```

---

For more examples and advanced usage patterns, see the [Usage Guide](USAGE.md) and [examples directory](../examples/).
