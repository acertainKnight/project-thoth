# Thoth Architecture

Technical deep-dive into the architecture, design patterns, and implementation of Thoth Research Assistant.

## Table of Contents

- [System Overview](#system-overview)
- [Microservices Architecture](#microservices-architecture)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Design Patterns](#design-patterns)
- [Performance Optimizations](#performance-optimizations)
- [Security](#security)

## System Overview

Thoth is a **production-ready microservices architecture** designed for academic research automation. The system consists of **7 specialized Docker containers**, **32 coordinated services**, and **54 MCP research tools**.

### High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐
│ Obsidian Plugin │────▶│  FastAPI Server │
│  (TypeScript)   │     │   (Port 8000)   │
└─────────────────┘     └────────┬────────┘
                                  │
                                  ▼
                      ┌──────────────────────┐
                      │   ServiceManager     │
                      │  (32 Services)       │
                      └────────┬─────────────┘
                               │
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
      ▼                        ▼                        ▼
┌──────────┐           ┌──────────────┐        ┌─────────────┐
│   MCP    │           │   Document   │        │  Discovery  │
│  Server  │           │   Pipeline   │        │   Engine    │
│(54 tools)│           │  (8 stages)  │        │             │
└──────────┘           └──────────────┘        └─────────────┘
      │                        │                        │
      ▼                        ▼                        ▼
┌──────────┐           ┌──────────────┐        ┌─────────────┐
│   Letta  │           │  Citation    │        │    ArXiv    │
│PostgreSQL│           │   System     │        │   Semantic  │
│+pgvector │           │ (6 stages)   │        │   Scholar   │
└──────────┘           └──────────────┘        └─────────────┘
```

### Design Principles

1. **Microservices**: Independent, focused services with clear boundaries
2. **Vault-Centric**: Single source of truth in Obsidian vault
3. **Hot-Reload**: Configuration changes without restart (dev mode)
4. **Graceful Degradation**: System works with subset of services
5. **Type Safety**: Pydantic models throughout
6. **Async-First**: Non-blocking I/O for scalability

## Microservices Architecture

### Container Services

#### 1. API Server (Dockerfile: `docker/api/Dockerfile`, ~200MB)
**Purpose**: REST API and WebSocket communication

**Technologies**:
- FastAPI for REST endpoints
- WebSocket for real-time streaming
- 11 routers (health, config, operations, research, chat, tools, etc.)

**Responsibilities**:
- HTTP API endpoints
- WebSocket connections
- Request validation (Pydantic)
- Service coordination
- Hot-reload configuration

**Exposed Ports**:
- Development: 8000
- Production: 8080

#### 2. MCP Server (Dockerfile: `docker/mcp/Dockerfile`, ~2.5GB)
**Purpose**: Model Context Protocol with 54 research tools

**Technologies**:
- FastAPI for HTTP/SSE transports
- JSON-RPC for protocol
- Asyncio for concurrent tool execution

**Responsibilities**:
- MCP protocol implementation
- 54 built-in research tools
- 3rd-party plugin system
- Tool parameter validation
- Streaming responses (SSE)

**Exposed Ports**:
- Development: 8001 (HTTP)
- Production: 8081 (SSE), 8082 (HTTP)

#### 3. PDF Monitor (Dockerfile: `docker/pdf-monitor/Dockerfile`, ~2.5GB)
**Purpose**: Automated PDF processing with Watchdog

**Technologies**:
- Watchdog for file monitoring
- OptimizedDocumentPipeline
- OCR libraries (tesseract)
- ML dependencies

**Responsibilities**:
- Monitor `_thoth/data/pdfs/` directory
- Trigger pipeline on new PDFs
- Handle file modifications
- Debounce rapid changes (2s)

**Size Reason**: Large due to OCR and ML dependencies for PDF processing

#### 4. Agent Service (Dockerfile: `docker/agent/Dockerfile`)
**Purpose**: Agent orchestration and coordination

**Responsibilities**:
- Agent lifecycle management
- Tool assignment
- Memory coordination with Letta

#### 5. Discovery Service (Dockerfile: `docker/discovery/Dockerfile`)
**Purpose**: Multi-source paper discovery

**Technologies**:
- Playwright for browser automation
- ArXiv API client
- Semantic Scholar API client

**Responsibilities**:
- ArXiv RSS/API discovery
- Semantic Scholar integration
- Browser-based scraping
- Automated scheduling (cron-like)

**Exposed Ports**:
- Development: 8004

#### 6. Letta Memory System (`letta/letta:latest`)
**Purpose**: Persistent agent memory with PostgreSQL+pgvector

**Technologies**:
- Letta framework
- PostgreSQL with pgvector extension
- FastAPI for REST API

**Responsibilities**:
- Agent memory persistence
- Cross-session continuity
- Salience-based memory management
- Vector similarity search

**Exposed Ports**:
- 8283 (REST API)
- 8284 (Nginx proxy for SSE, production only)

#### 7. PostgreSQL (`pgvector/pgvector:pg15`)
**Purpose**: Database backend with vector extension

**Responsibilities**:
- Letta memory storage
- Vector embeddings (pgvector)
- Agent state persistence
- Research question storage

**Exposed Ports**:
- Development: 5433 (external access)
- Production: Internal only

### Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| **Images** | Fresh build each time | Cached, optimized builds |
| **Volumes** | Host mounts for hot-reload | Named volumes |
| **Ports** | 8000-8004 | 8080-8082 |
| **Logging** | DEBUG level | INFO level |
| **Hot-Reload** | Enabled (~2s) | Disabled |
| **ChromaDB** | Running (port 8003) | Not deployed |
| **Discovery** | Running (port 8004) | Not deployed |
| **Resource Limits** | None | CPU/memory limits |
| **Replicas** | 1 per service | 1-3 per service |
| **Networks** | Single bridge | Frontend + backend isolation |

## Core Components

### Configuration System (src/thoth/config.py - 1425 lines)

**Architecture**:
```python
┌──────────────────────────────────────────────┐
│           Vault Detection                    │
│  1. OBSIDIAN_VAULT_PATH env var             │
│  2. THOTH_VAULT_PATH (legacy)               │
│  3. Auto-detect (_thoth/ directory)         │
│  4. Known location (~/Documents/thoth)      │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│      Load settings.json                      │
│  - Parse JSON to Pydantic models            │
│  - Validate all fields                      │
│  - Convert relative → absolute paths        │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│      Hot-Reload System (Dev Only)           │
│  - Watch settings.json for changes          │
│  - Trigger reload callbacks                 │
│  - Services re-initialize (~2s)             │
└──────────────────────────────────────────────┘
```

**Key Features**:
- **Single source of truth**: `vault/_thoth/settings.json`
- **Type-safe**: Pydantic models with validation
- **Hot-reload**: Dev mode reloads config in ~2 seconds
- **Path resolution**: Vault-relative → absolute conversion
- **Secrets separation**: API keys from `.env`, not settings.json

### Service Manager (src/thoth/services/service_manager.py - 284 lines)

**Dependency Injection Pattern**:
```python
ServiceManager
    │
    ├─ Initialize Phase 1: Core Services
    │   ├─ LLMService (no dependencies)
    │   ├─ ProcessingService (depends: LLMService)
    │   └─ ArticleService (depends: LLMService)
    │
    ├─ Initialize Phase 2: Path-Dependent
    │   ├─ QueryService (needs: queries_dir)
    │   ├─ DiscoveryService (needs: sources_dir)
    │   └─ RAGService (optional, needs embeddings extras)
    │
    ├─ Initialize Phase 3: External APIs
    │   ├─ APIGateway
    │   └─ LettaService (optional, needs memory extras)
    │
    ├─ Initialize Phase 4: Advanced Services
    │   ├─ CitationService
    │   ├─ PostgresService
    │   └─ ResearchQuestionService (depends: PostgresService)
    │
    └─ Initialize Phase 5: Discovery & Optimization
        ├─ DiscoveryManager (depends: AvailableSourceRepository)
        ├─ DiscoveryOrchestrator (depends: LLM, Manager, Postgres)
        ├─ CacheService (optional)
        └─ AsyncProcessingService (optional)
```

**Features**:
- **Centralized coordination**: Single point for all services
- **Lazy initialization**: Services created on first access
- **Optional services**: Graceful handling of missing extras
- **Dynamic access**: `manager.llm` returns LLMService instance

### MCP Server (src/thoth/mcp/server.py - 467 lines)

**Protocol Architecture**:
```
┌─────────────────────────────────────────────┐
│            MCP Client                        │
│  (Obsidian Plugin, CLI, or External)        │
└──────────────────┬──────────────────────────┘
                   │ JSON-RPC over HTTP/SSE
                   ▼
┌─────────────────────────────────────────────┐
│         MCPProtocolHandler                   │
│  - Parse JSON-RPC requests                  │
│  - Route to method handlers                 │
│  - Format responses                         │
└──────────────────┬──────────────────────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
      ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│   Tool   │ │Resource  │ │ Prompt   │
│ Registry │ │ Manager  │ │ Manager  │
└─────┬────┘ └──────────┘ └──────────┘
      │
      ▼
┌─────────────────────────────────────────────┐
│     54 Research Tools (16 modules)          │
│  - Query tools                              │
│  - Discovery tools                          │
│  - Citation tools                           │
│  - Article tools                            │
│  - Processing tools                         │
│  - PDF content tools                        │
│  - Advanced RAG tools                       │
│  - Analysis tools                           │
│  - Tag tools                                │
│  - Browser workflow tools                   │
│  - Web search tool                          │
│  - Settings tools                           │
│  - Data management tools                    │
│  - Custom index tools                       │
│  - Download PDF tool                        │
└─────────────────────────────────────────────┘
```

**Transports**:
- **HTTP** (port 8001/8082): Simple request/response
- **SSE** (port 8081): Server-Sent Events for streaming
- **Stdio**: CLI integration

### Document Pipeline (src/thoth/pipelines/optimized_document_pipeline.py - 489 lines)

**8-Stage Processing**:
```
PDF Input
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 1: Text Extraction                   │
│  - Extract text with pypdf                  │
│  - Handle malformed PDFs                    │
│  - Preserve structure                       │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 2: Metadata Extraction               │
│  - Extract title, authors, abstract         │
│  - LLM-assisted for complex cases           │
│  - Validate and normalize                   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 3: Citation Extraction               │
│  - Identify citation patterns               │
│  - Parse bibliography section               │
│  - Create Citation objects                  │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 4: Citation Enrichment               │
│  - Multi-resolver chain (6 stages)          │
│  - Batch processing for efficiency          │
│  - Add DOI, metadata, citation counts       │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 5: Semantic Chunking                 │
│  - Split into 200-500 token segments        │
│  - Preserve section structure               │
│  - Context-aware with LangChain             │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 6: Tag Generation                    │
│  - AI-generated tags via LLM                │
│  - Extract topics, methods, domains         │
│  - Consolidate across document              │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 7: Note Generation                   │
│  - Create markdown note with template       │
│  - Frontmatter + metadata + citations       │
│  - Save to notes_dir                        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 8: Index Building (Optional)         │
│  - Build vector embeddings (RAG)            │
│  - Add to ChromaDB                          │
│  - Update citation graph                    │
└─────────────────────────────────────────────┘
```

### Citation System (src/thoth/analyze/citations/ - 20 modules, 500K+ lines)

**6-Stage Resolution Chain**:
```
Citation String → "Smith et al. (2023)"
    │
    ▼
┌─────────────────────────────────────────────┐
│  Stage 1: Crossref Resolver (20K lines)     │
│  - DOI lookup via Crossref API              │
│  - Title/author search fallback             │
│  - Confidence scoring                       │
└──────────────────┬──────────────────────────┘
                   │ If not found/low confidence
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 2: OpenAlex Resolver (19K lines)     │
│  - Work ID lookup                           │
│  - Author disambiguation                    │
│  - Citation count enrichment                │
└──────────────────┬──────────────────────────┘
                   │ If not found/low confidence
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 3: ArXiv Resolver (7.4K lines)       │
│  - ArXiv ID lookup                          │
│  - Paper metadata extraction                │
│  - PDF URL retrieval                        │
└──────────────────┬──────────────────────────┘
                   │ If not found
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 4: Fuzzy Matcher (21K lines)         │
│  - String similarity algorithms             │
│  - Author name variants                     │
│  - Title normalization                      │
│  - Year proximity matching                  │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 5: Match Validator (18K lines)       │
│  - Confidence scoring (0.0-1.0)             │
│  - Field validation (title, authors, year)  │
│  - Threshold filtering (0.7 default)        │
│  - False positive detection                 │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 6: Decision Engine (18K lines)       │
│  - Multi-match resolution                   │
│  - Best match selection                     │
│  - Confidence aggregation                   │
│  - Final metadata package                   │
└──────────────────┬──────────────────────────┘
                   ▼
Enriched Citation (DOI, metadata, counts)
```

**Performance**:
- Batch processing: ~100 citations/minute
- Real-time enrichment: <1s per citation (with cache)
- Cache hit rate: 70-90% typical
- Parallel resolvers: 3-5x speedup

## Data Flow

### Document Processing Flow

```
User drops PDF → _thoth/data/pdfs/
    │
    ▼
PDF Monitor detects new file (Watchdog)
    │
    ▼
Trigger OptimizedDocumentPipeline
    │
    ├─ Extract text (pypdf)
    ├─ Extract metadata (LLM-assisted)
    ├─ Extract citations (regex patterns)
    ├─ Enrich citations (6-stage chain)
    ├─ Generate chunks (LangChain)
    ├─ Generate tags (LLM)
    ├─ Create markdown note (Jinja2 template)
    └─ Build index (ChromaDB, optional)
    │
    ▼
Note saved → _thoth/data/notes/paper_title.md
    │
    ▼
Obsidian detects new note (file watcher)
    │
    ▼
User reads note in Obsidian vault
```

### Agent Memory Flow

```
User sends message via Obsidian plugin
    │
    ▼
WebSocket connection to API Server (8000)
    │
    ▼
API routes to Letta REST API (8283)
    │
    ▼
Letta retrieves agent state from PostgreSQL+pgvector
    │
    ├─ Load conversation history
    ├─ Load agent memory (vector similarity)
    ├─ Load tool assignments
    └─ Load personality/instructions
    │
    ▼
Letta generates response with MCP tools
    │
    ├─ Call MCP Server (8001) for tool execution
    ├─ Stream response chunks via SSE
    └─ Update memory in PostgreSQL
    │
    ▼
API streams response back via WebSocket
    │
    ▼
Plugin displays in chat modal (real-time)
```

### Discovery Flow

```
User: "Find papers on transformers"
    │
    ▼
Context Analyzer (39K lines)
    ├─ Analyze vault notes for context
    ├─ Extract relevant topics
    ├─ Generate targeted search queries
    └─ Set relevance scoring criteria
    │
    ▼
Discovery Manager distributes to sources
    │
    ├─ ArXiv: RSS feed + API search
    ├─ Semantic Scholar: API query
    └─ Browser: Playwright automation
    │
    ▼
Aggregate results from all sources
    │
    ├─ Deduplicate by DOI/title (O(n log n))
    ├─ Score relevance (0-1 scale)
    └─ Filter by threshold (0.7 default)
    │
    ▼
Return ranked results to user
    │
    ▼
Optional: Download PDFs & process
```

## Technology Stack

### Backend (Python)

- **Python**: 3.10-3.12 (NOT 3.13)
- **FastAPI**: REST API framework with async support
- **Pydantic**: Data validation and settings management
- **Letta**: Persistent agent memory system
- **PostgreSQL+pgvector**: Vector database for embeddings
- **ChromaDB**: Development vector store
- **LangChain**: Text processing and chunking
- **NetworkX**: Citation graph analysis
- **Playwright**: Browser automation for discovery
- **Ruff**: Linting and formatting
- **pytest**: Testing framework (998 tests)
- **Hypothesis**: Property-based testing

### Frontend (TypeScript)

- **TypeScript**: Type-safe development
- **Obsidian API**: Plugin integration
- **esbuild**: Fast bundling
- **WebSocket**: Real-time communication

### Infrastructure

- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration
- **UV**: Fast Python package manager
- **Nginx**: SSE proxy for Letta (production)
- **GitHub Actions**: CI/CD pipeline

### AI/ML

- **Mistral**: Primary LLM provider
- **OpenRouter**: Multi-provider LLM routing
- **Anthropic Claude**: Analysis tasks (via OpenRouter)
- **Sentence Transformers**: Embedding generation (all-MiniLM-L6-v2)
- **OpenAI**: Optional LLM provider

## Design Patterns

### 1. Service-Oriented Architecture (SOA)

**ServiceManager** coordinates 32 independent services:
- Each service has single responsibility
- Services communicate through manager
- Dependency injection for loose coupling
- Optional services for graceful degradation

### 2. Repository Pattern

17 repositories abstract data access:
- BaseRepository provides common CRUD operations
- Caching layer built into repositories
- Type-safe queries with Pydantic models
- Connection pooling (asyncpg)

### 3. Pipeline Pattern

Document processing uses configurable stages:
- BasePipeline defines contract
- OptimizedDocumentPipeline implements 8 stages
- Each stage is independent and testable
- Stages can be skipped or customized

### 4. Plugin Architecture

MCP tools use plugin system:
- MCPTool base class defines interface
- 54 built-in tools across 16 modules
- 3rd-party plugin support
- Dynamic tool discovery and registration

### 5. Observer Pattern

Hot-reload system uses callbacks:
- Config registers reload callbacks
- Services subscribe to config changes
- Callbacks triggered on settings.json modification
- Services re-initialize with new config

## Performance Optimizations

### Caching Strategy

**Multi-Level Caching**:
1. **Request Cache** (API layer):
   - Cache GET requests (5 min TTL)
   - 70-90% hit rate typical
   - Automatic invalidation on updates

2. **Service Cache** (Service layer):
   - Cache expensive operations (LLM calls, API requests)
   - Configurable TTL per operation
   - Memory-efficient with size limits

3. **Database Cache** (Repository layer):
   - Query result caching
   - Connection pooling (10-50 connections)
   - Prepared statements

### Async/Await Throughout

- **Non-blocking I/O**: All I/O operations use async/await
- **Concurrent operations**: Process multiple requests simultaneously
- **Connection pooling**: Reuse database/HTTP connections
- **Streaming responses**: WebSocket for real-time updates

### Request Queue Management

- **Max concurrent**: 3 requests to prevent overload
- **Queue excess**: Additional requests queued
- **Exponential backoff**: Retry failed requests with increasing delay
- **Timeout handling**: Automatic cancellation of long-running requests

### Batch Processing

- **Citation enrichment**: Process 50-100 citations at once
- **Parallel resolvers**: Multiple API calls simultaneously
- **Chunked embeddings**: Generate 50 embeddings per batch
- **Database bulk inserts**: Insert 1000s of records efficiently

## Security

### Authentication & Authorization

- **API Keys**: Stored in environment variables, never in code
- **CORS**: Configurable origins for API access
- **Rate Limiting**: Prevent API abuse (optional)
- **JWT Tokens**: For stateful authentication (optional)

### Container Security

- **Non-root user**: All containers run as UID 1000:1000
- **Minimal base images**: Alpine/slim Python images
- **No secrets in images**: Environment variables for sensitive data
- **Network isolation**: Production uses frontend + backend networks
- **Security scanning**: Bandit for Python code analysis

### Data Protection

- **Vault-centric**: All user data in controlled location
- **No external transmission**: Data stays local unless explicitly sent to APIs
- **API key isolation**: Secrets separate from configuration
- **Encrypted storage**: PostgreSQL can use encryption at rest

### Dependency Management

- **Pinned versions**: Exact versions in pyproject.toml
- **Security scanning**: Dependabot for vulnerability alerts
- **Regular updates**: Automated dependency updates
- **Extras for optional features**: Minimize attack surface

---

This architecture provides a **scalable, maintainable, and secure** foundation for academic research automation. The microservices design enables independent development and deployment, while the unified configuration system simplifies operation.

For implementation details, see the [source code](../src/thoth/) and [component documentation](../README.md#key-features).
