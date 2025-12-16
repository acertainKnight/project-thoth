# Thoth Dependency Mapping by Service

## Service Analysis

### 1. **thoth-api** (REST API Server)
**Command**: `python -m thoth server start --api-host 0.0.0.0 --api-port 8000 --no-mcp --no-discovery`

**What it does**:
- FastAPI REST endpoints
- Database queries (SQLAlchemy + asyncpg)
- Research questions API
- Article management
- Dashboard data API

**Required Dependencies**:
- **Core**: FastAPI, uvicorn, pydantic, SQLAlchemy, asyncpg, aiofiles
- **API Features**: httpx, requests, arrow, json-repair
- **Discovery extras**: For ArxivPlugin (beautifulsoup4, lxml, feedparser)
- **NO NEED FOR**: LangChain, ChromaDB, Letta, sentence-transformers, pytorch

### 2. **thoth-mcp** (Model Context Protocol Server)
**Command**: `python -m thoth mcp http --host 0.0.0.0 --port 8001`

**What it does**:
- MCP protocol server for Claude integration
- Exposes research tools via MCP
- May need access to RAG/vector search

**Required Dependencies**:
- **Core**: FastAPI, uvicorn, pydantic
- **LangChain**: langchain-mcp-adapters, langchain-core
- **VectorDB**: chromadb, langchain-chroma (for RAG search)
- **Embeddings**: sentence-transformers (HEAVY - 500MB+)

### 3. **thoth-monitor** (PDF File Watcher)
**Command**: `python -m thoth monitor --optimized --recursive`

**What it does**:
- Watches /vault for new PDFs
- Extracts text from PDFs
- OCR via Mistral API
- Chunks text
- Generates embeddings
- Stores in ChromaDB

**Required Dependencies**:
- **Core**: watchdog, aiofiles
- **PDF**: pypdf, mistralai (for OCR API)
- **LangChain**: langchain, langchain-text-splitters, langchain-openai, langchain-anthropic
- **VectorDB**: chromadb, langchain-chroma
- **Embeddings**: sentence-transformers (HEAVY)
- **LLM**: openrouter, openai, instructor

### 4. **thoth-dashboard** (Discovery Dashboard Sync)
**Command**: `python -m thoth.cli.main research start-dashboard --check-interval 60`

**What it does**:
- Exports discovery results to markdown
- Watches dashboard folder for sentiment changes
- Downloads PDFs when articles are liked
- Updates database

**Required Dependencies**:
- **Core**: aiofiles, watchdog
- **Discovery**: For re-exporting (beautifulsoup4, lxml, feedparser)
- **PDF Download**: requests, httpx
- **NO NEED FOR**: LangChain, ChromaDB, embeddings, ML libraries

### 5. **thoth-agent** (Research Agent Service)
**Command**: `python -m thoth agent serve --host 0.0.0.0 --port 8005`

**What it does**:
- LangGraph agent workflows
- Multi-agent coordination
- Memory management via Letta
- RAG search via ChromaDB
- Complex research tasks

**Required Dependencies**:
- **ALL THE HEAVY STUFF**:
- **LangChain Full**: langgraph, langgraph-checkpoint, langchain-openai, langchain-anthropic
- **VectorDB**: chromadb, langchain-chroma
- **Embeddings**: sentence-transformers (HEAVY)
- **Memory**: letta, letta-mcp-server (HEAVY - nvidia libs)
- **LLM**: openrouter, openai, instructor
- **Discovery**: For research (scholarly, selenium, duckduckgo-search)

### 6. **thoth-discovery** (Discovery Scheduler Service)
**Command**: `python -m thoth discovery server`

**What it does**:
- Scheduled discovery from arXiv, PubMed, etc.
- Web scraping
- API calls to academic sources
- Stores in PostgreSQL (NOT ChromaDB)

**Required Dependencies**:
- **Core**: FastAPI, uvicorn, aiofiles
- **Discovery**: beautifulsoup4, lxml, feedparser, scholarly, selenium, fake-useragent, duckduckgo-search
- **Academic APIs**: networkx, bibtexparser, roman-numerals-py
- **NO NEED FOR**: LangChain, ChromaDB, embeddings, Letta, ML libraries

## Recommended Dependency Group Structure

```toml
[project]
dependencies = [
    # Absolute bare minimum - CLI, logging, config
    "click>=8.1.8",
    "loguru>=0.7.3",
    "python-dotenv>=1.0.1",
    "pydantic>=2.9.2",
    "pydantic-settings>=2.5.0",
]

[project.optional-dependencies]
# API Server (thoth-api)
api = [
    "fastapi>=0.115.12",
    "uvicorn>=0.32.0",
    "sqlalchemy>=2.0.39",
    "alembic>=1.13.0",
    "asyncpg",
    "aiofiles>=24.1.0",
    "httpx>=0.27.0",
    "requests>=2.32.3",
    "arrow>=1.3.0",
    "json-repair>=0.44.1",
    "jinja2>=3.1.6",
]

# Discovery module (thoth-api + thoth-dashboard + thoth-discovery)
discovery = [
    "beautifulsoup4>=4.13.2",
    "lxml>=5.3.0",
    "feedparser>=6.0.11",
    "networkx>=3.4.2",
    "scholarly>=1.7.11",
    "bibtexparser>=1.4.2",
    "selenium>=4.29.0",
    "fake-useragent>=2.1.0",
    "duckduckgo-search>=5.2",
    "roman-numerals-py>=3.1.0",
    "aiohttp>=3.8.5",
]

# MCP Server (thoth-mcp)
mcp = [
    "fastapi>=0.115.12",
    "uvicorn>=0.32.0",
    "langchain-mcp-adapters",
    "langchain-core>=0.3.45",
]

# PDF Processing (thoth-monitor + thoth-dashboard)
pdf = [
    "watchdog>=6.0.0",
    "pypdf>=5.3.1",
    "mistralai>=1.5.1",
    "aiofiles>=24.1.0",
]

# LangChain ecosystem (thoth-monitor + thoth-agent + thoth-mcp)
langchain = [
    "langchain>=0.3.21",
    "langchain-core>=0.3.45",
    "langchain-text-splitters>=0.3.7",
    "langchain-openai>=0.3.9",
    "langchain-anthropic>=0.1.8",
    "langgraph>=0.4.7",
    "langgraph-checkpoint>=2.0.26",
    "langgraph-sdk>=0.1.70",
    "langgraph-prebuilt>=0.2.1",
    "langsmith>=0.3.16",
    "openrouter>=0.0.19",
    "openai>=1.57.0",
    "instructor>=1.8.3",
    "tiktoken>=0.9.0",
    "websockets>=15.0.1",
]

# Vector database (thoth-monitor + thoth-agent + thoth-mcp)
# HEAVY: ~500MB with numpy/scipy dependencies
vectordb = [
    "chromadb>=0.5.0",
    "langchain-chroma>=0.1.0",
]

# Embeddings (thoth-monitor + thoth-agent + thoth-mcp)
# VERY HEAVY: ~2GB with PyTorch and transformers
embeddings = [
    "langchain-huggingface>=0.1.0",
    "sentence-transformers>=3.0.0",
]

# Advanced memory (thoth-agent only)
# EXTREMELY HEAVY: ~3GB with transformers, torch, nvidia libs
memory = [
    "letta>=0.9,<1.0",
    "letta-mcp-server>=0.1.0",
    "sqlite-vec>=0.1.6",
]

# Full agent (thoth-agent)
agent = [
    "thoth[langchain,vectordb,embeddings,memory,discovery,pdf]",
]

# Visualization (optional for all)
viz = [
    "matplotlib>=3.9.2",
    "plotly>=5.20.0",
    "grandalf>=0.8",
]
```

## Docker Build Commands

### thoth-api (Minimal - ~200MB)
```dockerfile
RUN uv sync --locked --no-install-project --extra api --extra discovery
```

### thoth-mcp (Medium - ~800MB)
```dockerfile
RUN uv sync --locked --no-install-project --extra mcp --extra langchain --extra vectordb --extra embeddings
```

### thoth-monitor (Heavy - ~2.5GB)
```dockerfile
RUN uv sync --locked --no-install-project --extra pdf --extra langchain --extra vectordb --extra embeddings
```

### thoth-dashboard (Minimal - ~150MB)
```dockerfile
RUN uv sync --locked --no-install-project --extra api --extra discovery --extra pdf
```

### thoth-agent (Maximum - ~4GB)
```dockerfile
RUN uv sync --locked --no-install-project --extra agent
```

### thoth-discovery (Medium - ~300MB)
```dockerfile
RUN uv sync --locked --no-install-project --extra api --extra discovery
```

## Size Estimates

- **Core only**: ~50MB
- **+ api**: ~150MB (+100MB)
- **+ discovery**: ~200MB (+50MB)
- **+ langchain**: ~500MB (+300MB)
- **+ vectordb**: ~800MB (+300MB)
- **+ embeddings**: ~2.5GB (+1.7GB - PyTorch)
- **+ memory (letta)**: ~4GB (+1.5GB - nvidia libs)

## Current Problem

Right now ALL containers install ALL dependencies (~4GB) including:
- nvidia-cublas-cu12 (374.9MB)
- nvidia-cusolver-cu12 (150.9MB)
- nvidia-cusparselt-cu12 (149.5MB)
- PyTorch (~2GB)
- sentence-transformers
- letta + transformers

But only **thoth-agent** actually needs these!

## Next Steps

1. Reorganize pyproject.toml with service-specific extras
2. Update each Dockerfile to install only required extras
3. Test each service independently
4. Measure container size reduction
5. Update docker-compose.yml if needed
