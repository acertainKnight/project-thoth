# Thoth API Reference

This document provides comprehensive documentation for all API endpoints available in the Thoth Research Assistant FastAPI server.

## 🔗 **External API Gateway Service**

The `ExternalAPIGateway` service provides a centralized interface for making external API calls with built-in rate limiting, caching, and retry logic.

### **Features**
- **Rate Limiting**: Configurable requests per second throttling
- **Response Caching**: Time-based caching with SHA256 cache keys
- **Retry Logic**: Exponential backoff for failed requests (0s, 1s, 3s delays)
- **Service Endpoints**: Configurable mapping of service names to base URLs
- **Error Handling**: Comprehensive error handling with service-specific exceptions

### **Configuration**
Configure the API gateway through environment variables with `API_GATEWAY_` prefix:

```bash
API_GATEWAY_RATE_LIMIT=5.0              # Requests per second
API_GATEWAY_CACHE_EXPIRY=3600           # Cache expiry in seconds
API_GATEWAY_DEFAULT_TIMEOUT=15          # Request timeout in seconds
API_GATEWAY_ENDPOINTS='{"service1": "https://api.example.com", "service2": "https://api2.example.com"}'
```

### **Usage Example**
```python
from thoth.services import ExternalAPIGateway

# Initialize gateway
gateway = ExternalAPIGateway(config=config)
gateway.initialize()

# Make GET request
response = gateway.get("service1", path="/users", params={"limit": 10})

# Make POST request
response = gateway.post("service1", path="/data", data={"key": "value"})

# Clear cache
gateway.clear_cache()
```

## 🎯 **Base URL and Authentication**

### **Base URL**
```
http://localhost:8000  # Default local setup
http://0.0.0.0:8000    # Docker/WSL setup
```

### **Authentication**
The API currently does not require authentication for local use. For production deployments, consider implementing authentication middleware.

### **Content Types**
- **Request**: `application/json`
- **Response**: `application/json`

## 📋 **Health and Status Endpoints**

### **Health Check**
Check if the API server is running and responsive.

```http
GET /health
```

#### **Response**
```json
{
  "status": "healthy",
  "service": "thoth-obsidian-api"
}
```

#### **Example**
```bash
curl http://localhost:8000/health
```

### **Agent Status**
Check the status of the research agent and its capabilities.

```http
GET /agent/status
```

#### **Response Scenarios**

**Agent Running (200)**
```json
{
  "status": "running",
  "agent_initialized": true,
  "tools_count": 15,
  "message": "Research agent is running and ready"
}
```

**Agent Not Initialized (503)**
```json
{
  "status": "not_initialized",
  "agent_initialized": false,
  "message": "Research agent not initialized"
}
```

**Agent Error (500)**
```json
{
  "status": "error",
  "agent_initialized": false,
  "error": "Error description",
  "message": "Research agent encountered an error"
}
```

#### **Example**
```bash
curl http://localhost:8000/agent/status
```

## 🤖 **Research Agent Endpoints**

### **Chat with Research Agent**
Interactive chat endpoint for conversational research assistance.

```http
POST /research/chat
```

#### **Request Body**
```json
{
  "message": "string",
  "conversation_id": "string (optional)",
  "timestamp": "integer (optional)"
}
```

#### **Response**
```json
{
  "response": "string",
  "tool_calls": [
    {
      "tool_name": "string",
      "arguments": {},
      "result": "string"
    }
  ],
  "error": "string (optional)"
}
```

#### **Examples**

**Basic Chat**
```bash
curl -X POST http://localhost:8000/research/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What discovery sources do I have available?",
    "conversation_id": "session-123"
  }'
```

**Research Query**
```bash
curl -X POST http://localhost:8000/research/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create an ArXiv source for machine learning papers",
    "conversation_id": "setup-session"
  }'
```

**Knowledge Base Query**
```bash
curl -X POST http://localhost:8000/research/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Search my knowledge base for transformer architectures",
    "conversation_id": "research-session"
  }'
```

### **Direct Research Query**
Structured research endpoint for specific research tasks.

```http
POST /research/query
```

#### **Request Body**
```json
{
  "query": "string",
  "type": "string (default: 'quick_research')",
  "max_results": "integer (default: 5)",
  "include_citations": "boolean (default: true)"
}
```

#### **Response**
```json
{
  "results": "string",
  "response": "string",
  "error": "string (optional)"
}
```

#### **Example**
```bash
curl -X POST http://localhost:8000/research/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest developments in transformer architectures",
    "type": "comprehensive_research",
    "max_results": 10,
    "include_citations": true
  }'
```

### **List Agent Tools**
Get a list of all available tools for the research agent.

```http
GET /agent/tools
```

#### **Response**
```json
{
  "tools": [
    {
      "name": "list_discovery_sources",
      "description": "List all configured discovery sources",
      "parameters": {}
    },
    {
      "name": "search_knowledge",
      "description": "Search papers and notes in knowledge base",
      "parameters": {
        "query": "string",
        "k": "integer",
        "filter": "object"
      }
    }
  ],
  "count": 15
}
```

#### **Example**
```bash
curl http://localhost:8000/agent/tools
```

## ⚙️ **Configuration Management Endpoints**

### **Get Agent Configuration**
Retrieve the current agent configuration (sanitized, no sensitive data).

```http
GET /agent/config
```

#### **Response**
```json
{
  "directories": {
    "workspace_dir": "/path/to/project-thoth",
    "pdf_dir": "/path/to/project-thoth/data/pdf",
    "notes_dir": "/path/to/project-thoth/data/notes",
    "queries_dir": "/path/to/project-thoth/planning/queries",
    "agent_storage_dir": "/path/to/project-thoth/knowledge/agent"
  },
  "api_server": {
    "host": "127.0.0.1",
    "port": 8000,
    "base_url": "http://localhost:8000"
  },
  "llm_models": {
    "llm_model": "openai/gpt-4o-mini",
    "research_agent_model": "anthropic/claude-3-5-sonnet:beta"
  },
  "discovery": {
    "auto_start_scheduler": false,
    "default_max_articles": 50
  },
  "has_api_keys": {
    "mistral": true,
    "openrouter": true
  }
}
```

#### **Example**
```bash
curl http://localhost:8000/agent/config
```

### **Update Agent Configuration**
Update agent configuration dynamically without restarting.

```http
POST /agent/config
```

#### **Request Body**
```json
{
  "api_keys": {
    "mistral": "string (optional)",
    "openrouter": "string (optional)",
    "web_search": "string (optional)"
  },
  "settings": {
    "log_level": "string (optional)",
    "endpoint_host": "string (optional)",
    "endpoint_port": "integer (optional)"
  },
  "directories": {
    "workspace": "string (optional)",
    "pdf": "string (optional)",
    "notes": "string (optional)"
  }
}
```

#### **Response**
```json
{
  "status": "success",
  "message": "Configuration updated successfully",
  "updated_keys": ["API_OPENROUTER_KEY", "WORKSPACE_DIR"],
  "note": "Agent restart required for changes to take full effect"
}
```

#### **Example**
```bash
curl -X POST http://localhost:8000/agent/config \
  -H "Content-Type: application/json" \
  -d '{
    "api_keys": {
      "openrouter": "sk-or-v1-new-key-here"
    },
    "settings": {
      "log_level": "DEBUG"
    }
  }'
```

### **Restart Agent**
Restart the research agent with optional configuration updates.

```http
POST /agent/restart
```

#### **Request Body** (Optional)
```json
{
  "update_config": "boolean (default: true)",
  "new_config": {
    "api_keys": {},
    "settings": {},
    "directories": {}
  }
}
```

#### **Response Scenarios**

**Successful Restart**
```json
{
  "status": "success",
  "message": "Agent restart initiated",
  "old_pid": 12345,
  "method": "process_restart"
}
```

**Fallback Reinitialization**
```json
{
  "status": "success",
  "message": "Agent reinitialized successfully (fallback)",
  "method": "reinitialize",
  "restart_error": "Process restart failed: reason"
}
```

#### **Example**
```bash
curl -X POST http://localhost:8000/agent/restart \
  -H "Content-Type: application/json" \
  -d '{
    "update_config": true,
    "new_config": {
      "api_keys": {
        "openrouter": "new-api-key"
      }
    }
  }'
```

### **Sync Obsidian Settings**
Synchronize settings from Obsidian plugin to the backend.

```http
POST /agent/sync-settings
```

#### **Request Body**
```json
{
  "mistral_api_key": "string (optional)",
  "openrouter_api_key": "string (optional)",
  "workspace_directory": "string (optional)",
  "obsidian_directory": "string (optional)",
  "remote_url": "string (optional)",
  "remote_mode": "boolean (optional)"
}
```

#### **Response**
```json
{
  "status": "success",
  "message": "Settings synchronized successfully",
  "synced_keys": ["API_OPENROUTER_KEY", "WORKSPACE_DIR"]
}
```

#### **Example**
```bash
curl -X POST http://localhost:8000/agent/sync-settings \
  -H "Content-Type: application/json" \
  -d '{
    "openrouter_api_key": "sk-or-v1-your-key",
    "workspace_directory": "/home/user/project-thoth",
    "remote_mode": false
  }'
```

## 📄 **File Management Endpoints**

### **Download PDF**
Download a PDF from a URL and save it to the configured PDF directory.

```http
GET /download-pdf?url={pdf_url}
```

#### **Parameters**
- `url` (required): The URL of the PDF to download

#### **Response**
```json
{
  "status": "success",
  "message": "PDF downloaded successfully to /path/to/file.pdf",
  "file_path": "/path/to/file.pdf"
}
```

#### **Error Response**
```json
{
  "detail": "Failed to download PDF: error description"
}
```

#### **Example**
```bash
curl "http://localhost:8000/download-pdf?url=https://arxiv.org/pdf/1706.03762.pdf"
```

### **View Markdown**
View the contents of a markdown file from the notes directory.

```http
GET /view-markdown?path={file_path}
```

#### **Parameters**
- `path` (required): Path to the markdown file relative to the notes directory

#### **Response**
```json
{
  "status": "success",
  "content": "# Paper Title\n\nContent of the markdown file...",
  "file_path": "/full/path/to/file.md"
}
```

#### **Error Response**
```json
{
  "detail": "File not found"
}
```

#### **Example**
```bash
curl "http://localhost:8000/view-markdown?path=research/transformer_paper.md"
```

## 🔧 **Error Handling**

### **HTTP Status Codes**

| Code | Meaning | Description |
|------|---------|-------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Invalid request parameters |
| `404` | Not Found | Resource not found |
| `500` | Internal Server Error | Server error occurred |
| `503` | Service Unavailable | Agent not initialized or unavailable |

### **Error Response Format**
```json
{
  "detail": "Error description"
}
```

### **Common Error Scenarios**

#### **Agent Not Initialized**
```bash
# Response (503)
{
  "detail": "Research agent not initialized"
}
```

#### **Invalid Configuration**
```bash
# Response (500)
{
  "detail": "Failed to update config: Invalid API key format"
}
```

#### **File Not Found**
```bash
# Response (404)
{
  "detail": "File not found"
}
```

## 📚 **Integration Examples**

### **Obsidian Plugin Integration**

**Connect to Agent**
```javascript
async function connectToThoth() {
  try {
    const response = await fetch('http://localhost:8000/agent/status');
    const status = await response.json();
    console.log('Agent status:', status);
    return status.agent_initialized;
  } catch (error) {
    console.error('Failed to connect to Thoth:', error);
    return false;
  }
}
```

**Send Chat Message**
```javascript
async function sendChatMessage(message, conversationId = null) {
  try {
    const response = await fetch('http://localhost:8000/research/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        conversation_id: conversationId || `obsidian-${Date.now()}`,
        timestamp: Date.now()
      })
    });

    const result = await response.json();
    return result.response;
  } catch (error) {
    console.error('Chat error:', error);
    return 'Error communicating with research agent.';
  }
}
```

**Update Configuration**
```javascript
async function updateThothConfig(apiKeys, directories) {
  try {
    const response = await fetch('http://localhost:8000/agent/config', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        api_keys: apiKeys,
        directories: directories
      })
    });

    const result = await response.json();
    console.log('Config updated:', result);
    return result.status === 'success';
  } catch (error) {
    console.error('Config update error:', error);
    return false;
  }
}
```

### **Python Integration**

**Simple Client**
```python
import requests
import json

class ThothAPIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def health_check(self):
        """Check if the API is healthy."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()

    def chat(self, message, conversation_id=None):
        """Send a chat message to the research agent."""
        data = {
            "message": message,
            "conversation_id": conversation_id or f"python-client-{hash(message)}"
        }
        response = requests.post(
            f"{self.base_url}/research/chat",
            json=data
        )
        return response.json()

    def get_agent_status(self):
        """Get the agent status."""
        response = requests.get(f"{self.base_url}/agent/status")
        return response.json()

    def download_pdf(self, url):
        """Download a PDF from URL."""
        response = requests.get(
            f"{self.base_url}/download-pdf",
            params={"url": url}
        )
        return response.json()

# Usage example
client = ThothAPIClient()

# Check health
print(client.health_check())

# Chat with agent
response = client.chat("List my discovery sources")
print(response["response"])

# Download a paper
result = client.download_pdf("https://arxiv.org/pdf/1706.03762.pdf")
print(f"Downloaded to: {result['file_path']}")
```

### **Shell Script Integration**

**Basic API Testing Script**
```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

echo "🔍 Testing Thoth API..."

# Health check
echo "Health check:"
curl -s "$BASE_URL/health" | jq '.'

echo -e "\n📊 Agent status:"
curl -s "$BASE_URL/agent/status" | jq '.'

echo -e "\n🛠️ Available tools:"
curl -s "$BASE_URL/agent/tools" | jq '.count'

echo -e "\n💬 Chat test:"
curl -s -X POST "$BASE_URL/research/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you help me with?", "conversation_id": "test-session"}' \
  | jq '.response'

echo -e "\n✅ API test complete!"
```

## 🚀 **Development and Testing**

### **Running the API Server**

**Local Development**
```bash
# Start with auto-reload
uv run python -m thoth api --host 127.0.0.1 --port 8000 --reload

# Start for WSL/Docker access
uv run python -m thoth api --host 0.0.0.0 --port 8000

# Custom port
uv run python -m thoth api --port 8001
```

**Docker Development**
```bash
# Start development container
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### **API Documentation**

**Interactive Documentation**
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

**OpenAPI Schema**
```bash
curl http://localhost:8000/openapi.json
```

### **Testing Endpoints**

**Using curl**
```bash
# Test all endpoints
bash scripts/test_api.sh

# Test specific functionality
curl -X POST http://localhost:8000/research/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test message"}'
```

**Using Python requests**
```python
import requests

# Test chat functionality
response = requests.post(
    "http://localhost:8000/research/chat",
    json={"message": "What discovery sources are available?"}
)
print(response.json())
```

**Using Postman/Insomnia**
Import the OpenAPI schema from `http://localhost:8000/openapi.json` into your API testing tool.

---

This API reference provides comprehensive documentation for all Thoth API endpoints. The API is designed to be RESTful and follows standard HTTP conventions. For additional examples and integration patterns, refer to the Obsidian plugin source code and the examples directory.
