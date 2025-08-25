# Thoth Architecture Documentation

This document provides a comprehensive overview of the Thoth Research Assistant system architecture, including its components, design patterns, and integration points.

## System Overview

Thoth is designed as a modular, scalable research assistant system with the following key characteristics:

- **Microservice Architecture**: Loosely coupled services with clear boundaries
- **Event-Driven Design**: Asynchronous processing with message passing
- **Plugin-Based Extensibility**: Modular components for easy customization
- **Multi-Protocol Support**: REST API, WebSocket, and MCP integration
- **AI-First Design**: LLM integration at the core of all operations

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Obsidian      │   CLI Tools     │   External Clients         │
│   Plugin        │                 │   (API/WebSocket)           │
└─────────────────┴─────────────────┴─────────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────────┐
│                        API Gateway                               │
├─────────────────────────────┼─────────────────────────────────────┤
│   FastAPI Server           │   MCP Protocol Server              │
│   - REST Endpoints         │   - Stdio Transport                │
│   - WebSocket Support      │   - HTTP Transport                 │
│   - CORS Configuration     │   - SSE Transport                  │
└─────────────────────────────┼─────────────────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────────┐
│                      Service Layer                               │
├─────────────────┬───────────┼───────────┬─────────────────────────┤
│   Agent         │  LLM      │  RAG      │   Document              │
│   Services      │  Router   │  Service  │   Processing            │
├─────────────────┼───────────┼───────────┼─────────────────────────┤
│   Discovery     │  Citation │  Tag      │   Knowledge             │
│   Service       │  Service  │  Service  │   Graph                 │
└─────────────────┴───────────┴───────────┴─────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────────────────────┐
│                      Data Layer                                  │
├─────────────────┬───────────┼───────────┬─────────────────────────┤
│   Vector        │  Document │  Cache    │   Knowledge             │
│   Database      │  Store    │  Layer    │   Graph DB              │
│   (ChromaDB)    │  (Files)  │  (Memory) │   (NetworkX)            │
└─────────────────┴───────────┴───────────┴─────────────────────────┘
```

## Core Components

### 1. Service Manager (`src/thoth/services/service_manager.py`)

The central orchestrator that manages all Thoth services with dependency injection:

```python
class ServiceManager:
    """Central service manager coordinating all Thoth services."""

    def __init__(self, config: ThothConfig | None = None):
        self.config = config or get_config()
        self._services = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all services with proper dependencies."""
        # Core services with dependency injection
        self._services['llm'] = LLMService(config=self.config)
        self._services['processing'] = ProcessingService(
            config=self.config, llm_service=self._services['llm']
        )
        self._services['rag'] = RAGService(config=self.config)
        self._services['discovery'] = DiscoveryService(config=self.config)
        self._services['citation'] = CitationService(config=self.config)

        # Advanced services (optional, with availability checks)
        if OPTIMIZED_SERVICES_AVAILABLE:
            self._services['cache'] = CacheService(config=self.config)
            self._services['async_processing'] = AsyncProcessingService(
                config=self.config, llm_service=self._services['llm']
            )
```

**Responsibilities:**
- Service lifecycle and dependency management
- Cross-service communication and event routing
- Configuration management and environment setup
- Health monitoring and performance tracking
- Resource allocation and cleanup

### 2. Pipeline System (`src/thoth/pipelines/`)

Modular document processing pipelines:

#### Base Pipeline Architecture
```python
class Pipeline(ABC):
    """Abstract base class for all processing pipelines."""

    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """Process input data through the pipeline."""
        pass

    def add_stage(self, stage: PipelineStage):
        """Add a processing stage to the pipeline."""
        self.stages.append(stage)
```

#### Document Processing Pipeline
```
PDF Input → Text Extraction → Chunking → Embedding → Vector Storage
    ↓              ↓             ↓          ↓            ↓
Metadata    →  Citation    → Tag      → Analysis → Knowledge Graph
Extraction     Extraction    Generation   Processing   Integration
```

### 3. LLM Integration (`src/thoth/services/llm/`)

Multi-provider LLM support with intelligent routing:

#### LLM Router
```python
class LLMRouter:
    """Routes LLM requests to appropriate providers based on task type."""

    def __init__(self):
        self.providers = {
            'openai': OpenAIClient(),
            'anthropic': AnthropicClient(),
            'mistral': MistralClient(),
            'openrouter': OpenRouterClient()
        }

    async def route_request(self, task_type: str, **kwargs) -> LLMResponse:
        """Route request to best provider for task type."""
        provider = self.select_provider(task_type, **kwargs)
        return await provider.generate(**kwargs)
```

#### Task-Specific Routing
- **Analysis Tasks**: Anthropic Claude (better reasoning)
- **Generation Tasks**: OpenAI GPT-4 (creative output)
- **Code Tasks**: Specialized models via OpenRouter
- **Bulk Processing**: Cost-effective models (Mistral)

### 4. RAG System (`src/thoth/rag/`)

Retrieval-Augmented Generation implementation:

#### Vector Store Management
```python
class VectorStore:
    """Manages document embeddings and similarity search."""

    def __init__(self, embedding_model: str = "sentence-transformers/all-mpnet-base-v2"):
        self.embedding_function = SentenceTransformerEmbeddings(
            model_name=embedding_model
        )
        self.chroma_client = chromadb.PersistentClient()

    async def add_documents(self, documents: List[Document]):
        """Add documents to vector store with embeddings."""

    async def similarity_search(self, query: str, k: int = 10) -> List[Document]:
        """Perform similarity search and return relevant documents."""
```

#### RAG Pipeline
```
User Query → Query Embedding → Similarity Search → Context Retrieval
     ↓              ↓              ↓                    ↓
Response     ← LLM Generation ← Context + Query ← Document Ranking
Generation     with Context     Assembly          and Filtering
```

### 5. Discovery System (`src/thoth/discovery/`)

Automated research paper discovery and collection:

#### Discovery Manager
```python
class DiscoveryManager:
    """Coordinates multiple discovery sources and strategies."""

    def __init__(self):
        self.plugins = {
            'arxiv': ArxivPlugin(),
            'semantic_scholar': SemanticScholarPlugin(),
            'web_search': WebSearchPlugin(),
            'chrome_extension': ChromeExtensionPlugin()
        }

    async def discover_papers(self, query: str, sources: List[str] = None) -> List[Paper]:
        """Discover papers from multiple sources."""
```

#### Discovery Sources
- **ArXiv**: Academic preprints
- **Semantic Scholar**: Peer-reviewed papers
- **Web Search**: General academic content
- **Chrome Extension**: User-browsed papers
- **RSS Feeds**: Journal updates

### 5.5. Memory System (`src/thoth/memory/`)

Advanced persistent memory system built on Letta framework for comprehensive conversation and research context management:

#### Memory Architecture
```python
class ThothMemoryStore:
    """
    Letta-based memory store with multi-scope persistent memory management.

    Features:
    - Salience-based memory retention
    - Multi-scope memory (core/episodic/archival)
    - Cross-session persistence
    - Contextual memory enrichment
    """
```

#### Memory Scopes
- **Core Memory**: Long-term persistent facts and preferences
- **Episodic Memory**: Conversation history and interactions
- **Archival Memory**: Deep storage for large context and historical data

#### Memory Pipeline Architecture
```
Memory Input → Salience Scoring → Filtering → Enrichment → Storage
     ↓              ↓              ↓           ↓           ↓
Context       → Importance    → Relevance → Enhanced  → Persistent
Assessment      Analysis        Filtering    Metadata    Storage
```

#### LangGraph Checkpointer Integration
```python
class LettaCheckpointer(BaseCheckpointer):
    """LangGraph-compatible checkpointer using Letta memory backend."""

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, ...):
        """Store conversation checkpoints with memory context."""

    async def aget(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """Retrieve conversation state with memory integration."""
```

#### Memory Features
- **Salience-Based Retention**: Intelligent memory importance scoring
- **Session Management**: Cross-session conversation continuity
- **Health Monitoring**: Built-in system health checks and recovery
- **Fallback Management**: Graceful degradation during system issues
- **Vector Integration**: Semantic search across memory contexts

### 6. MCP Integration (`src/thoth/mcp/`)

Model Context Protocol implementation for AI agent interoperability:

#### MCP Server Architecture
```python
class MCPServer:
    """Main MCP server handling protocol messages and tool execution."""

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.tool_registry = MCPToolRegistry(service_manager)
        self.resource_manager = MCPResourceManager()
        self.transport_manager = TransportManager()

    async def handle_message(self, message: JSONRPCMessage) -> JSONRPCResponse:
        """Route MCP messages to appropriate handlers."""
```

#### Transport Layers
- **Stdio Transport**: Direct CLI integration
- **HTTP Transport**: Web-based clients
- **SSE Transport**: Server-sent events for streaming

#### Tool Registry
```python
# Available MCP tools
tools = [
    "thoth_search_papers",      # Search research papers
    "thoth_analyze_document",   # Analyze specific documents
    "thoth_generate_summary",   # Generate research summaries
    "thoth_extract_citations",  # Extract and analyze citations
    "thoth_build_knowledge",    # Build knowledge graphs
    "thoth_query_rag",         # Query RAG system
]
```

## Data Architecture

### 1. Document Storage

#### File System Organization
```
workspace/
├── pdfs/                   # Original PDF documents
│   ├── raw/               # Unprocessed PDFs
│   └── processed/         # Processed with metadata
├── data/
│   ├── documents/         # Extracted text and metadata
│   ├── chunks/           # Processed text chunks
│   ├── embeddings/       # Vector embeddings
│   └── cache/            # Temporary processing cache
├── knowledge/
│   ├── graphs/           # Knowledge graph data
│   ├── citations/        # Citation networks
│   └── tags/            # Tag hierarchies
└── logs/                 # System logs
```

#### Document Metadata Schema
```json
{
  "document_id": "uuid",
  "title": "Paper Title",
  "authors": ["Author 1", "Author 2"],
  "abstract": "Paper abstract text",
  "publication_date": "2024-01-15",
  "venue": "Conference/Journal Name",
  "doi": "10.1000/182",
  "citations": [
    {
      "title": "Cited Paper",
      "authors": ["Cited Author"],
      "year": 2023
    }
  ],
  "processing_metadata": {
    "extraction_confidence": 0.95,
    "ocr_required": false,
    "language": "en",
    "page_count": 12
  }
}
```

### 2. Vector Database (ChromaDB)

#### Collection Strategy
```python
# Separate collections for different content types
collections = {
    "papers_full": "Complete paper content",
    "papers_abstracts": "Abstract-only collection",
    "citations": "Citation text and metadata",
    "figures": "Figure captions and descriptions"
}
```

#### Embedding Strategy
- **Primary Model**: `sentence-transformers/all-mpnet-base-v2`
- **Specialized Models**:
  - Academic papers: `allenai/scibert_scivocab_uncased`
  - Code content: `microsoft/codebert-base`
- **Chunking Strategy**: Semantic chunking with 512-token overlap

### 3. Knowledge Graph (NetworkX)

#### Graph Schema
```python
# Node types
node_types = {
    "paper": {"title", "authors", "year", "venue"},
    "author": {"name", "affiliations", "h_index"},
    "concept": {"name", "category", "definition"},
    "venue": {"name", "type", "impact_factor"}
}

# Edge types
edge_types = {
    "cites": {"weight", "context"},
    "authored_by": {"position", "corresponding"},
    "published_in": {"year", "volume", "issue"},
    "related_to": {"strength", "type"}
}
```

## API Architecture

### 1. REST API Design

#### Endpoint Structure
```
/api/v1/
├── chat/
│   ├── sessions/              # Chat session management
│   └── messages/             # Message operations
├── documents/
│   ├── upload                # Document upload
│   ├── process               # Processing operations
│   └── search                # Document search
├── knowledge/
│   ├── query                 # Knowledge graph queries
│   ├── export                # Graph export
│   └── build                 # Graph construction
├── discovery/
│   ├── start                 # Start discovery
│   ├── status                # Discovery status
│   └── results               # Discovery results
└── system/
    ├── health                # Health checks
    ├── status                # System status
    └── metrics               # Performance metrics
```

#### Authentication & Security
```python
# API Key authentication for external clients
class APIKeyAuth:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def verify_request(self, request: Request) -> bool:
        return request.headers.get("X-API-Key") == self.api_key

# Rate limiting
class RateLimiter:
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.request_history = defaultdict(list)
```

### 2. WebSocket Architecture

#### Connection Management
```python
class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_groups: Dict[str, Set[str]] = {}

    async def broadcast_to_group(self, group: str, message: dict):
        """Broadcast message to all connections in a group."""
```

#### Message Types
```python
message_types = {
    "chat_message": {"session_id", "message", "response"},
    "processing_update": {"document_id", "status", "progress"},
    "discovery_update": {"query", "found_count", "status"},
    "system_notification": {"type", "message", "timestamp"}
}
```

## Plugin Architecture

### 1. Discovery Plugins

#### Plugin Interface
```python
class DiscoveryPlugin(ABC):
    """Base class for discovery plugins."""

    @abstractmethod
    async def discover(self, query: str, max_results: int) -> List[Document]:
        """Discover documents based on query."""
        pass

    @abstractmethod
    def get_supported_sources(self) -> List[str]:
        """Return list of supported source types."""
        pass
```

#### Plugin Registration
```python
class PluginManager:
    """Manages plugin lifecycle and registration."""

    def __init__(self):
        self.plugins: Dict[str, DiscoveryPlugin] = {}

    def register_plugin(self, name: str, plugin: DiscoveryPlugin):
        """Register a new discovery plugin."""
        self.plugins[name] = plugin

    def discover_from_source(self, source: str, query: str) -> List[Document]:
        """Use specific plugin for discovery."""
        return self.plugins[source].discover(query)
```

### 2. Processing Plugins

#### Custom Pipeline Stages
```python
class PipelineStage(ABC):
    """Base class for pipeline processing stages."""

    @abstractmethod
    async def process(self, document: Document) -> Document:
        """Process document and return modified version."""
        pass

# Example: Custom citation extractor
class CustomCitationExtractor(PipelineStage):
    async def process(self, document: Document) -> Document:
        # Custom citation extraction logic
        document.citations = self.extract_citations(document.content)
        return document
```

## Integration Patterns

### 1. Obsidian Plugin Integration

#### Communication Flow
```
Obsidian Plugin ←→ WebSocket/HTTP ←→ FastAPI Server ←→ Service Manager
                                         ↓
                                  Individual Services
                                         ↓
                                    Data Storage
```

#### Plugin Architecture
```typescript
// Main plugin class
export default class ThothPlugin extends Plugin {
    settings: ThothSettings;
    apiClient: APIUtilities;
    chatModal: MultiChatModal;

    async onload() {
        // Initialize API connection
        this.apiClient = new APIUtilities(this.settings);

        // Register commands
        this.addCommand({
            id: 'open-research-chat',
            name: 'Open Research Chat',
            callback: () => this.openChatModal()
        });
    }
}
```

### 2. External API Integration

#### Client Libraries
```python
# Python client
class ThothClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def chat(self, message: str, session_id: str = None) -> ChatResponse:
        """Send chat message and get response."""

    def upload_document(self, file_path: str) -> DocumentResponse:
        """Upload document for processing."""

    def search_papers(self, query: str, limit: int = 10) -> List[Paper]:
        """Search papers in knowledge base."""
```

#### JavaScript client
```javascript
class ThothAPI {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
    }

    async chat(message, sessionId = null) {
        const response = await fetch(`${this.baseURL}/chat/messages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId })
        });
        return response.json();
    }
}
```

## Scalability Considerations

### 1. Horizontal Scaling

#### Service Decomposition
- Each service can be deployed independently
- Load balancing across service instances
- Database sharding for large document collections

#### Microservice Deployment
```yaml
# docker-compose.yml
version: '3.8'
services:
  thoth-api:
    image: thoth:latest
    ports: ["8000:8000"]
    environment:
      - SERVICE_MODE=api

  thoth-worker:
    image: thoth:latest
    environment:
      - SERVICE_MODE=worker
    depends_on: [redis, postgres]

  thoth-discovery:
    image: thoth:latest
    environment:
      - SERVICE_MODE=discovery
```

### 2. Performance Optimization

#### Caching Strategy
```python
class CacheManager:
    """Multi-level caching for improved performance."""

    def __init__(self):
        self.memory_cache = TTLCache(maxsize=1000, ttl=300)
        self.redis_cache = redis.Redis()
        self.disk_cache = DiskCache("./cache")

    async def get(self, key: str) -> Any:
        # Try memory cache first
        if key in self.memory_cache:
            return self.memory_cache[key]

        # Try Redis cache
        redis_value = await self.redis_cache.get(key)
        if redis_value:
            self.memory_cache[key] = redis_value
            return redis_value

        # Try disk cache
        return self.disk_cache.get(key)
```

#### Async Processing
```python
# Background task processing
class TaskQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.workers = []

    async def add_task(self, task: Callable):
        await self.queue.put(task)

    async def worker(self):
        while True:
            task = await self.queue.get()
            try:
                await task()
            except Exception as e:
                logger.error(f"Task failed: {e}")
            finally:
                self.queue.task_done()
```

## Security Architecture

### 1. Data Protection

#### Encryption
- API keys encrypted at rest
- Document content encrypted in transit
- Vector embeddings anonymized

#### Access Control
```python
class AccessControl:
    def __init__(self):
        self.permissions = {
            "read_documents": ["user", "admin"],
            "write_documents": ["admin"],
            "system_admin": ["admin"]
        }

    def check_permission(self, user_role: str, permission: str) -> bool:
        return user_role in self.permissions.get(permission, [])
```

### 2. API Security

#### Input Validation
```python
from pydantic import BaseModel, validator

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

    @validator('message')
    def validate_message(cls, v):
        if len(v) > 10000:
            raise ValueError('Message too long')
        return v.strip()
```

#### Rate Limiting & Monitoring
```python
class SecurityMiddleware:
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.request_logger = RequestLogger()

    async def __call__(self, request: Request, call_next):
        # Check rate limits
        if not self.rate_limiter.allow_request(request):
            raise HTTPException(429, "Rate limit exceeded")

        # Log request
        self.request_logger.log_request(request)

        return await call_next(request)
```

## Monitoring & Observability

### 1. Health Monitoring

#### Health Checks
```python
class HealthMonitor:
    async def check_system_health(self) -> HealthStatus:
        checks = {
            "database": await self.check_database(),
            "vector_store": await self.check_vector_store(),
            "llm_providers": await self.check_llm_providers(),
            "disk_space": await self.check_disk_space()
        }

        return HealthStatus(
            status="healthy" if all(checks.values()) else "degraded",
            checks=checks
        )
```

### 2. Performance Metrics

#### Metrics Collection
```python
class MetricsCollector:
    def __init__(self):
        self.request_counter = Counter('thoth_requests_total')
        self.response_time = Histogram('thoth_response_time_seconds')
        self.active_connections = Gauge('thoth_active_connections')

    def record_request(self, endpoint: str, method: str, status: int, duration: float):
        self.request_counter.labels(endpoint=endpoint, method=method, status=status).inc()
        self.response_time.labels(endpoint=endpoint).observe(duration)
```

### 3. Logging Strategy

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Usage throughout the application
logger.info(
    "document_processed",
    document_id=doc_id,
    processing_time=duration,
    extracted_citations=len(citations),
    user_id=user_id
)
```

---

This architecture provides a solid foundation for a scalable, maintainable research assistant system while maintaining flexibility for future enhancements and integrations.
