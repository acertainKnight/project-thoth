# Thoth Services Documentation

This document provides detailed information about the service-oriented architecture of Thoth, including individual service responsibilities, actual APIs, and integration patterns.

## Service Architecture Overview

Thoth uses a microservice-like architecture where each service handles a specific domain of functionality. All services are coordinated through the `ServiceManager` and follow consistent patterns for health monitoring, configuration, and error handling.

## Core Services

### 1. LLM Service (`src/thoth/services/llm_service.py`)

Manages language model interactions with multiple provider support and client caching.

**Responsibilities:**
- LLM client creation and caching
- Multi-provider support (OpenAI, Anthropic, OpenRouter)
- Structured output generation with Pydantic schemas
- Prompt template management
- Error handling and retries

**Key Methods:**
```python
class LLMService:
    def get_client(self, model: str = None, temperature: float = None,
                   max_tokens: int = None, use_rate_limiter: bool = True, **kwargs) -> Any
    def get_llm(self, model: str = None, **kwargs) -> Any  # Alias for get_client
    def get_structured_client(self, schema: type[BaseModel], model: str = None,
                              method: str = 'json_schema', **kwargs) -> Any
    def create_prompt_template(self, template: str, input_variables: list[str]) -> ChatPromptTemplate
    def invoke_with_retry(self, client: Any, messages: list, max_retries: int = 3) -> Any
    def get_model_config(self, model_type: str) -> dict[str, Any]
    def clear_cache(self) -> None
    def health_check(self) -> dict[str, str]
```

### 2. RAG Service (`src/thoth/services/rag_service.py`)

Manages retrieval-augmented generation and vector search using ChromaDB integration.

**Responsibilities:**
- Document indexing and embedding
- Semantic search and retrieval
- Knowledge base management
- File and directory processing

**Key Methods:**
```python
class RAGService:
    def index_file(self, file_path: Path) -> list[str]
    def index_directory(self, directory: Path, pattern: str = "**/*.{md,txt,pdf}",
                        max_files: int = None, force_reindex: bool = False) -> dict[str, Any]
    def search(self, query: str, k: int = 10, filter_dict: dict = None,
               include_metadata: bool = True, min_similarity: float = 0.0) -> list[dict]
    def ask_question(self, question: str, k: int = 5, min_similarity: float = 0.1,
                     include_sources: bool = True, model: str = None) -> dict[str, Any]
    def get_statistics(self) -> dict[str, Any]
    def clear_index(self) -> None
    def index_knowledge_base(self, force_reindex: bool = False) -> dict[str, Any]
    def health_check(self) -> dict[str, str]
```

### 3. Discovery Service (`src/thoth/services/discovery_service.py`)

Automated research paper discovery from multiple sources with source management.

**Supported Sources:**
- ArXiv (academic preprints)
- Semantic Scholar (peer-reviewed papers)
- Google Scholar (web scraping)
- Web search integration
- RSS feeds

**Key Methods:**
```python
class DiscoveryService:
    def create_source(self, source: DiscoverySource) -> bool
    def get_source(self, name: str) -> DiscoverySource | None
    def list_sources(self, active_only: bool = False) -> list[DiscoverySource]
    def update_source(self, source: DiscoverySource) -> bool
    def delete_source(self, name: str) -> bool
    def run_discovery(self, source_name: str = None, max_articles: int = None,
                      filter_enabled: bool = True) -> dict[str, Any]
```

### 4. Citation Service (`src/thoth/services/citation_service.py`)

Citation extraction, validation, and network analysis with paper tracking.

**Responsibilities:**
- Citation extraction from documents
- Citation formatting and validation
- Academic source tracking
- Citation network analysis

**Key Methods:**
```python
class CitationService:
    def extract_citations(self, text: str, document_title: str = None,
                          max_citations: int = 100, confidence_threshold: float = 0.7) -> list[dict]
    def format_citation(self, citation_data: dict, style: str = "apa") -> str
    def track_citations(self, paper_title: str, citations: list[dict]) -> dict[str, Any]
    def get_citation_network(self, paper_title: str = None, max_depth: int = 2) -> dict[str, Any]
    def search_articles(self, query: str) -> list[dict[str, Any]]
```

### 5. Service Manager (`src/thoth/services/service_manager.py`)

Central orchestrator managing all services with dependency injection.

**Architecture Pattern:**
```python
class ServiceManager:
    def __init__(self, config: ThothConfig = None):
        self.config = config or get_config()
        self._services = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all services with proper dependencies."""
        # Core services
        self._services['llm'] = LLMService(config=self.config)
        self._services['rag'] = RAGService(config=self.config)
        self._services['discovery'] = DiscoveryService(config=self.config)
        self._services['citation'] = CitationService(config=self.config)

        # Optional services
        if OPTIMIZED_SERVICES_AVAILABLE:
            self._services['cache'] = CacheService(config=self.config)
            self._services['async_processing'] = AsyncProcessingService(
                config=self.config, llm_service=self._services['llm']
            )
```

**Service Access:**
```python
# Via property access
service_manager.llm  # Returns LLMService instance
service_manager.rag  # Returns RAGService instance

# Via get_service method
service_manager.get_service('llm')  # Returns LLMService instance
```

## Advanced Services

### Cache Service (`src/thoth/services/cache_service.py`)
*Optional service available when optimized dependencies installed*

**Responsibilities:**
- Multi-tier caching (memory, disk, distributed)
- Cache invalidation strategies
- Performance optimization

### Async Processing Service (`src/thoth/services/async_processing_service.py`)
*Optional service for background processing*

**Responsibilities:**
- Background task processing
- Document processing pipelines
- Async LLM operations

## Service Integration Patterns

### Configuration Management
All services receive configuration through dependency injection:
```python
service = LLMService(config=thoth_config)
```

### Error Handling
Services use structured error handling with ServiceError:
```python
try:
    client = llm_service.get_client(model="gpt-4")
except ServiceError as e:
    logger.error(f"Service error: {e}")
```

### Health Monitoring
All services implement health_check() method:
```python
health_status = service.health_check()
# Returns: {"status": "healthy", "details": {...}}
```

### Service Dependencies
Services are initialized in dependency order:
1. Core services (LLM, RAG, Discovery, Citation)
2. Dependent services (Processing, Note, Query)
3. Optional services (Cache, Async Processing)

## Usage Examples

### Using LLM Service
```python
# Get a basic client
llm = service_manager.llm.get_client(model="anthropic/claude-3-sonnet")

# Get structured output client
from pydantic import BaseModel
class Summary(BaseModel):
    title: str
    main_points: list[str]

structured_llm = service_manager.llm.get_structured_client(Summary)
```

### Using RAG Service
```python
# Index documents
service_manager.rag.index_directory(Path("./papers"))

# Search knowledge base
results = service_manager.rag.search("attention mechanisms", k=5)

# Ask questions
answer = service_manager.rag.ask_question("What are transformers?")
```

### Using Discovery Service
```python
# Create discovery source
source = DiscoverySource(
    name="ml_papers",
    source_type="arxiv",
    query="machine learning transformers"
)
service_manager.discovery.create_source(source)

# Run discovery
results = service_manager.discovery.run_discovery("ml_papers")
```

This documentation reflects the actual implementation as of the current codebase version.
