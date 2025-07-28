# Thoth Configuration Guide

This comprehensive guide covers all configuration options, environment variables, and setup procedures for the Thoth Research Assistant system.

## 🎯 **Quick Setup Checklist**

### **Essential Configuration (5 minutes)**
1. **Copy environment file**: `cp .env.example .env`
2. **Set API keys**: Add your OpenRouter API key (minimum required)
3. **Set directories**: Configure workspace paths for your setup
4. **Test installation**: Run `thoth --help` to verify installation

### **Required API Keys**
- **OpenRouter API Key**: Get from [openrouter.ai](https://openrouter.ai) - **REQUIRED**
- **Mistral API Key**: Get from [console.mistral.ai](https://console.mistral.ai) - Optional for OCR

### **Optional API Keys**
- **Serper API Key**: Get from [serper.dev](https://serper.dev) - For web search
- **OpenCitations API Key**: Get from [opencitations.net](https://opencitations.net) - For citation data
- **Semantic Scholar API Key**: Get from [semanticscholar.org](https://semanticscholar.org) - For paper metadata

## 📋 **Complete Configuration Reference**

### **1. API Keys Configuration** (`API_*`)

Control external service access for various Thoth features.

```bash
# Required for core functionality
API_OPENROUTER_KEY="sk-or-v1-your-openrouter-key-here"

# Optional for PDF OCR (recommended)
API_MISTRAL_KEY="your-mistral-api-key-here"

# Optional additional services
API_OPENAI_KEY=""                    # Direct OpenAI access (alternative to OpenRouter)
API_ANTHROPIC_KEY=""                 # Direct Anthropic access (alternative to OpenRouter)
API_OPENCITATIONS_KEY=""             # Citation metadata enhancement
API_SEMANTICSCHOLAR_API_KEY=""       # Paper metadata from Semantic Scholar
API_WEB_SEARCH_KEY=""                # Serper.dev for web search
API_WEB_SEARCH_PROVIDERS="serper,duckduckgo"  # Available: serper, duckduckgo, scrape
```

#### **API Key Setup Instructions**

**OpenRouter (Required)**
1. Visit [openrouter.ai](https://openrouter.ai)
2. Create account and add credits ($5-10 recommended for starting)
3. Generate API key in dashboard
4. Set `API_OPENROUTER_KEY` in your `.env` file

**Mistral (Recommended)**
1. Visit [console.mistral.ai](https://console.mistral.ai)
2. Create account and add credits
3. Generate API key
4. Set `API_MISTRAL_KEY` in your `.env` file

**Web Search (Optional)**
1. Visit [serper.dev](https://serper.dev) for Serper API
2. Create account (100 free searches)
3. Set `API_WEB_SEARCH_KEY` and include "serper" in `API_WEB_SEARCH_PROVIDERS`

### **2. LLM Model Configuration**

#### **Primary LLM Configuration** (`LLM_*`)

Controls the main language model used for content analysis and note generation.

```bash
# Model selection (choose based on your needs and budget)
LLM_MODEL="mistralai/mixtral-8x7b-instruct:nitro"      # Balanced performance/cost
# LLM_MODEL="openai/gpt-4o-mini"                       # Fast and affordable
# LLM_MODEL="anthropic/claude-3-5-sonnet:beta"         # High quality, more expensive
# LLM_MODEL="google/gemini-2.0-flash-exp"              # Google's latest model

# Model parameters
LLM_MODEL_SETTINGS_TEMPERATURE="0.7"                    # Creativity (0.0-1.0)
LLM_MODEL_SETTINGS_MAX_TOKENS="500000"                  # Maximum output length
LLM_MODEL_SETTINGS_TOP_P="1.0"                         # Nucleus sampling
LLM_MODEL_SETTINGS_FREQUENCY_PENALTY="0.0"             # Repetition reduction
LLM_MODEL_SETTINGS_PRESENCE_PENALTY="0.0"              # Topic diversity
LLM_MODEL_SETTINGS_STREAMING="False"                   # Streaming responses
LLM_MODEL_SETTINGS_USE_RATE_LIMITER="True"            # Rate limiting

# Document processing strategy
LLM_DOC_PROCESSING="auto"                               # auto, direct, refine, map_reduce
LLM_MAX_OUTPUT_TOKENS="500000"                         # Generation limit
LLM_MAX_CONTEXT_LENGTH="32000"                         # Model context window
LLM_CHUNK_SIZE="4000"                                  # Text chunk size for processing
LLM_CHUNK_OVERLAP="200"                                # Overlap between chunks
LLM_REFINE_THRESHOLD_MULTIPLIER="1.2"                 # When to use refine strategy
LLM_MAP_REDUCE_THRESHOLD_MULTIPLIER="3.0"             # When to use map-reduce strategy
```

#### **Specialized LLM Configurations**

**Citation Processing** (`CITATION_LLM_*`)
```bash
CITATION_LLM_MODEL="openai/gpt-4o-mini"               # Fast model for citations
CITATION_LLM_MAX_OUTPUT_TOKENS="10000"                # Smaller outputs for citations
CITATION_LLM_MAX_CONTEXT_LENGTH="16000"               # Context for citation processing
CITATION_CITATION_BATCH_SIZE="10"                     # Citations per batch (1-20)
```

**Tag Management** (`TAG_LLM_*`)
```bash
TAG_LLM_CONSOLIDATE_MODEL="google/gemini-flash-1.5-8b"  # Tag consolidation
TAG_LLM_SUGGEST_MODEL="google/gemini-flash-1.5-8b"      # Tag suggestions
TAG_LLM_MAP_MODEL="mistralai/ministral-3b"              # Fast tag mapping
TAG_LLM_MAX_OUTPUT_TOKENS="10000"                       # Tag processing output
TAG_LLM_MAX_CONTEXT_LENGTH="8000"                       # Tag context window
```

**Research Agent** (`RESEARCH_AGENT_LLM_*`)
```bash
RESEARCH_AGENT_LLM_MODEL="anthropic/claude-3-5-sonnet:beta"  # Conversational agent
RESEARCH_AGENT_LLM_MAX_OUTPUT_TOKENS="50000"                 # Agent responses
RESEARCH_AGENT_LLM_MAX_CONTEXT_LENGTH="200000"               # Long conversations
```

**Article Filtering** (`SCRAPE_FILTER_LLM_*`)
```bash
SCRAPE_FILTER_LLM_MODEL="google/gemini-2.0-flash-exp"  # Fast article evaluation
SCRAPE_FILTER_LLM_MAX_OUTPUT_TOKENS="5000"             # Filter decisions
SCRAPE_FILTER_LLM_MAX_CONTEXT_LENGTH="32000"           # Article analysis context
```

#### **Model Selection Guide**

| Use Case | Recommended Model | Why |
|----------|------------------|-----|
| **Budget-conscious** | `openai/gpt-4o-mini` | Excellent value, fast |
| **Balanced** | `mistralai/mixtral-8x7b-instruct:nitro` | Good quality/speed/cost |
| **High Quality** | `anthropic/claude-3-5-sonnet:beta` | Best reasoning and analysis |
| **Latest Features** | `google/gemini-2.0-flash-exp` | Cutting-edge capabilities |
| **Citation Processing** | `openai/gpt-4o-mini` | Fast, accurate for structured tasks |
| **Tag Management** | `google/gemini-flash-1.5-8b` | Efficient for classification |

### **3. Directory Configuration**

Controls where Thoth stores different types of files.

```bash
# Base directories (relative to workspace or absolute paths)
WORKSPACE_DIR="/path/to/project-thoth"          # Main project directory
PDF_DIR="data/pdf"                              # Original PDF files
MARKDOWN_DIR="data/markdown"                    # Converted markdown files
NOTES_DIR="data/notes"                          # Generated Obsidian notes
OUTPUT_DIR="data/output"                        # Processing outputs
KNOWLEDGE_BASE_DIR="data/knowledge"             # Knowledge base storage
TEMPLATES_DIR="templates"                       # Note templates
PROMPTS_DIR="templates/prompts"                 # LLM prompts

# Specialized directories
QUERIES_DIR="planning/queries"                  # Research query definitions
AGENT_STORAGE_DIR="knowledge/agent"             # Agent-managed files
GRAPH_STORAGE_PATH="knowledge/citations.graphml"  # Citation graph storage

# Discovery system directories
DISCOVERY_SOURCES_DIR="data/discovery/sources"      # Source configurations
DISCOVERY_RESULTS_DIR="data/discovery/results"      # Discovery results
CHROME_EXTENSION_CONFIGS_DIR="data/discovery/chrome_configs"  # Chrome configs
```

#### **Directory Setup for Different Scenarios**

**Local Development**
```bash
WORKSPACE_DIR="/home/user/projects/project-thoth"
PDF_DIR="data/pdf"                    # Creates: /home/user/projects/project-thoth/data/pdf
NOTES_DIR="/home/user/Documents/Obsidian Vault/Research"  # Direct to Obsidian
```

**Docker Setup**
```bash
WORKSPACE_DIR="/app"                  # Container workspace
PDF_DIR="data/pdf"                   # Container volumes
NOTES_DIR="data/notes"               # Mapped to host via volumes
```

**Network Storage**
```bash
WORKSPACE_DIR="/mnt/nas/research/thoth"
PDF_DIR="papers"                     # Network-attached storage
NOTES_DIR="/mnt/nas/obsidian/vault/research"
```

### **4. API Server Configuration** (`ENDPOINT_*`)

Controls the web API server for Obsidian integration.

```bash
ENDPOINT_HOST="127.0.0.1"            # Localhost only (secure)
# ENDPOINT_HOST="0.0.0.0"            # All interfaces (for Docker/WSL)
ENDPOINT_PORT="8000"                 # API server port
ENDPOINT_BASE_URL="http://localhost:8000"  # Full URL for links
ENDPOINT_AUTO_START="False"          # Start with monitor
```

#### **API Server Scenarios**

**Local Only (Default)**
```bash
ENDPOINT_HOST="127.0.0.1"
ENDPOINT_PORT="8000"
ENDPOINT_BASE_URL="http://127.0.0.1:8000"
```

**WSL + Windows**
```bash
ENDPOINT_HOST="0.0.0.0"              # Accept from Windows
ENDPOINT_PORT="8000"
ENDPOINT_BASE_URL="http://localhost:8000"
```

**Docker Container**
```bash
ENDPOINT_HOST="0.0.0.0"              # Accept external connections
ENDPOINT_PORT="8000"
ENDPOINT_BASE_URL="http://localhost:8000"
```

**Production Server**
```bash
ENDPOINT_HOST="0.0.0.0"
ENDPOINT_PORT="8000"
ENDPOINT_BASE_URL="https://thoth.yourdomain.com"
```

### **5. API Gateway Configuration** (`API_GATEWAY_*`)

The External API Gateway provides centralized management for external API calls with built-in rate limiting, caching, and retry logic.

```bash
# Rate limiting
API_GATEWAY_RATE_LIMIT="5.0"                    # Requests per second allowed
API_GATEWAY_CACHE_EXPIRY="3600"                 # Cache expiry time in seconds (1 hour)
API_GATEWAY_DEFAULT_TIMEOUT="15"                # Request timeout in seconds

# Service endpoints (JSON format)
API_GATEWAY_ENDPOINTS='{
  "semantic_scholar": "https://api.semanticscholar.org",
  "opencitations": "https://opencitations.net/index/coci/api/v1",
  "arxiv": "http://export.arxiv.org",
  "crossref": "https://api.crossref.org"
}'
```

#### **API Gateway Features**
- **Rate Limiting**: Prevents API quota exhaustion with configurable throttling
- **Response Caching**: SHA256-based caching reduces redundant requests
- **Retry Logic**: Exponential backoff for transient failures (0s, 1s, 3s delays)
- **Service Mapping**: Configure multiple external services with friendly names
- **Error Handling**: Comprehensive error tracking and logging

#### **Usage Examples**
```python
from thoth.services import ExternalAPIGateway

# Initialize with config
gateway = ExternalAPIGateway(config=config)

# Make requests to configured services
papers = gateway.get("semantic_scholar", path="/graph/v1/paper/search",
                    params={"query": "transformers", "limit": 10})

citations = gateway.get("opencitations", path="/citations",
                       params={"doi": "10.1038/nature12373"})
```

#### **Rate Limiting Guidelines**
| Service | Recommended Rate | Notes |
|---------|-----------------|-------|
| **Semantic Scholar** | 100/minute (1.67/s) | Has generous limits |
| **OpenCitations** | 60/minute (1.0/s) | Conservative approach |
| **ArXiv** | 3/second | Bulk download limits |
| **CrossRef** | 50/second | High-volume API |
| **General External APIs** | 5.0/second | Default safe rate |

### **6. RAG System Configuration** (`RAG_*`)

Controls the knowledge base and search functionality.

```bash
# Embedding configuration
RAG_EMBEDDING_MODEL="openai/text-embedding-3-small"  # Embedding model
RAG_EMBEDDING_BATCH_SIZE="100"                       # Batch processing size

# Vector database
RAG_VECTOR_DB_PATH="knowledge/vector_db"             # Database location
RAG_COLLECTION_NAME="thoth_knowledge"                # Collection name

# Document processing
RAG_CHUNK_SIZE="1000"                                # Text chunk size
RAG_CHUNK_OVERLAP="200"                              # Chunk overlap

# Question answering
RAG_QA_MODEL="openai/gpt-4o-mini"                   # QA model
RAG_QA_TEMPERATURE="0.2"                            # QA creativity (lower = focused)
RAG_QA_MAX_TOKENS="2000"                            # QA response length
RAG_RETRIEVAL_K="4"                                 # Documents for context
```

#### **RAG Performance Tuning**

**For Large Collections (1000+ papers)**
```bash
RAG_EMBEDDING_BATCH_SIZE="50"       # Smaller batches for stability
RAG_CHUNK_SIZE="800"                # Smaller chunks for precision
RAG_RETRIEVAL_K="6"                 # More context for complex queries
```

**For Fast Responses**
```bash
RAG_EMBEDDING_MODEL="openai/text-embedding-3-small"  # Faster embedding
RAG_QA_MODEL="openai/gpt-4o-mini"                   # Faster QA model
RAG_RETRIEVAL_K="3"                                 # Fewer documents
```

**For High Quality**
```bash
RAG_EMBEDDING_MODEL="openai/text-embedding-3-large"  # Better embeddings
RAG_QA_MODEL="anthropic/claude-3-5-sonnet:beta"     # Better reasoning
RAG_RETRIEVAL_K="5"                                 # More context
```

### **6. Discovery System Configuration** (`DISCOVERY_*`)

Controls automated paper discovery and scraping.

```bash
DISCOVERY_AUTO_START_SCHEDULER="False"      # Auto-start scheduler
DISCOVERY_DEFAULT_MAX_ARTICLES="50"         # Default article limit
DISCOVERY_DEFAULT_INTERVAL_MINUTES="60"     # Default check interval
DISCOVERY_RATE_LIMIT_DELAY="1.0"           # Delay between requests (seconds)

# Chrome extension integration
DISCOVERY_CHROME_EXTENSION_ENABLED="True"   # Enable Chrome extension
DISCOVERY_CHROME_EXTENSION_PORT="8765"      # Chrome extension port
```

### **7. Citation Processing Configuration** (`CITATION_*`)

Controls citation extraction and metadata enhancement.

```bash
CITATION_LINK_FORMAT="uri"                  # Citation link format (uri, wikilink)
CITATION_STYLE="IEEE"                       # Citation style (IEEE, APA, MLA)
CITATION_USE_OPENCITATIONS="True"           # Use OpenCitations API
CITATION_USE_SCHOLARLY="False"              # Use Google Scholar (rate limited)
CITATION_USE_SEMANTICSCHOLAR="True"         # Use Semantic Scholar API
CITATION_USE_ARXIV="False"                  # Use ArXiv API
CITATION_CITATION_BATCH_SIZE="10"           # Citations per LLM batch (1-20)
```

#### **Citation Performance Optimization**

**For Speed**
```bash
CITATION_CITATION_BATCH_SIZE="20"           # Larger batches (may reduce accuracy)
CITATION_USE_OPENCITATIONS="False"          # Skip external APIs
CITATION_USE_SEMANTICSCHOLAR="False"
```

**For Accuracy**
```bash
CITATION_CITATION_BATCH_SIZE="5"            # Smaller batches for precision
CITATION_USE_OPENCITATIONS="True"           # Enable all metadata sources
CITATION_USE_SEMANTICSCHOLAR="True"
```

### **8. Monitoring and Logging** (`LOG_*`)

Controls system logging and debugging.

```bash
LOG_LEVEL="INFO"                            # DEBUG, INFO, WARNING, ERROR
LOG_LOGFORMAT="{time} | {level} | {file}:{line} | {function} | {message}"
LOG_DATEFORMAT="YYYY-MM-DD HH:mm:ss"        # Date format
LOG_FILENAME="logs/thoth.log"               # Log file location
LOG_FILEMODE="a"                            # Append mode
LOG_FILE_LEVEL="INFO"                       # File log level
```

#### **Logging Scenarios**

**Development/Debugging**
```bash
LOG_LEVEL="DEBUG"                           # Verbose logging
LOG_FILE_LEVEL="DEBUG"                      # Debug to file
```

**Production**
```bash
LOG_LEVEL="INFO"                            # Standard logging
LOG_FILE_LEVEL="WARNING"                    # Only warnings/errors to file
```

**Troubleshooting**
```bash
LOG_LEVEL="DEBUG"                           # Detailed information
LOG_FILENAME="logs/debug-$(date +%Y%m%d).log"  # Daily debug logs
```

### **9. File Monitoring** (`MONITOR_*`)

Controls automatic PDF processing when files are added.

```bash
MONITOR_AUTO_START="False"                  # Auto-start monitor
MONITOR_WATCH_INTERVAL="10"                 # Check interval (seconds)
MONITOR_BULK_PROCESS_SIZE="10"              # Files per batch
```

## 🎯 **Configuration Profiles**

### **Development Profile**

Optimized for development and testing with detailed logging and local-only access.

```bash
# API Keys (minimal for development)
API_OPENROUTER_KEY="your-key"

# Development-friendly models (cost-effective)
LLM_MODEL="openai/gpt-4o-mini"
CITATION_LLM_MODEL="openai/gpt-4o-mini"
RAG_QA_MODEL="openai/gpt-4o-mini"

# Local development paths
WORKSPACE_DIR="."
NOTES_DIR="/path/to/test-vault"

# Debug settings
LOG_LEVEL="DEBUG"
ENDPOINT_HOST="127.0.0.1"
ENDPOINT_AUTO_START="True"

# Fast processing
CITATION_CITATION_BATCH_SIZE="20"
RAG_RETRIEVAL_K="3"
```

### **Production Profile**

Optimized for production deployment with security and performance.

```bash
# All API keys configured
API_OPENROUTER_KEY="your-key"
API_MISTRAL_KEY="your-key"
API_OPENCITATIONS_KEY="your-key"

# High-quality models
LLM_MODEL="anthropic/claude-3-5-sonnet:beta"
RESEARCH_AGENT_LLM_MODEL="anthropic/claude-3-5-sonnet:beta"
RAG_QA_MODEL="openai/gpt-4o"

# Production paths
WORKSPACE_DIR="/app"
NOTES_DIR="/data/notes"

# Production settings
LOG_LEVEL="INFO"
ENDPOINT_HOST="0.0.0.0"
ENDPOINT_AUTO_START="False"

# Balanced performance
CITATION_CITATION_BATCH_SIZE="10"
RAG_RETRIEVAL_K="4"
```

### **Budget-Conscious Profile**

Minimizes costs while maintaining functionality.

```bash
# Essential API keys only
API_OPENROUTER_KEY="your-key"

# Cost-effective models
LLM_MODEL="openai/gpt-4o-mini"
CITATION_LLM_MODEL="openai/gpt-4o-mini"
TAG_LLM_CONSOLIDATE_MODEL="mistralai/ministral-3b"
RAG_QA_MODEL="openai/gpt-4o-mini"

# Disable expensive features
CITATION_USE_OPENCITATIONS="False"
CITATION_USE_SEMANTICSCHOLAR="False"

# Optimize for efficiency
CITATION_CITATION_BATCH_SIZE="20"
RAG_EMBEDDING_BATCH_SIZE="200"
RAG_RETRIEVAL_K="3"
```

## 🔧 **Environment Setup**

### **Creating Configuration File**

1. **Copy template**: `cp .env.example .env`
2. **Edit configuration**: Use your preferred editor to modify `.env`
3. **Validate settings**: Run `thoth --help` to test configuration loading
4. **Test API connections**: Use agent or API server to verify functionality

### **Docker Environment Setup**

Create `docker-compose.override.yml` for local customization:

```yaml
services:
  thoth:
    environment:
      - API_OPENROUTER_KEY=your-actual-key
      - LLM_MODEL=openai/gpt-4o-mini
      - LOG_LEVEL=DEBUG
    volumes:
      - ./local-data:/app/data
      - /path/to/your/vault:/app/data/notes
```

### **WSL Environment Setup**

For Windows Subsystem for Linux:

```bash
# In WSL, create .env file
cd /home/user/project-thoth
cp .env.example .env

# Edit configuration for WSL
nano .env

# Key settings for WSL:
ENDPOINT_HOST="0.0.0.0"              # Allow Windows access
WORKSPACE_DIR="/home/user/project-thoth"
NOTES_DIR="/mnt/c/Users/User/Documents/Obsidian Vault/Research"
```

## 🚨 **Troubleshooting Configuration**

### **Common Configuration Issues**

#### **API Key Errors**
```bash
# Test API connectivity
curl -H "Authorization: Bearer $API_OPENROUTER_KEY" \
     "https://openrouter.ai/api/v1/models"

# Verify key format
echo $API_OPENROUTER_KEY | wc -c  # Should be ~60+ characters
```

#### **Path Issues**
```bash
# Check directory existence
ls -la "$WORKSPACE_DIR"
ls -la "$PDF_DIR"

# Check permissions
ls -ld "$NOTES_DIR"
```

#### **Model Availability**
```bash
# List available models via OpenRouter
curl -H "Authorization: Bearer $API_OPENROUTER_KEY" \
     "https://openrouter.ai/api/v1/models" | grep -i "mixtral"
```

#### **Port Conflicts**
```bash
# Check if port is in use
netstat -an | grep :8000
lsof -i :8000

# Use different port
ENDPOINT_PORT="8001"
```

### **Configuration Validation Script**

Create `validate_config.py`:

```python
#!/usr/bin/env python3
"""Validate Thoth configuration."""

from thoth.utilities.config import get_config
from pathlib import Path

def validate_config():
    """Validate configuration and report issues."""
    config = get_config()

    # Check API keys
    if not config.api_keys.openrouter_key:
        print("❌ Missing required OpenRouter API key")
    else:
        print("✅ OpenRouter API key configured")

    # Check directories
    for dir_name, dir_path in [
        ("PDF", config.pdf_dir),
        ("Notes", config.notes_dir),
        ("Output", config.output_dir),
    ]:
        if not Path(dir_path).exists():
            print(f"⚠️  {dir_name} directory does not exist: {dir_path}")
        else:
            print(f"✅ {dir_name} directory exists: {dir_path}")

    # Check model configuration
    print(f"✅ Primary LLM model: {config.llm_config.model}")
    print(f"✅ API server: {config.api_server_config.host}:{config.api_server_config.port}")

if __name__ == "__main__":
    validate_config()
```

Run with: `python validate_config.py`

## 📖 **Advanced Configuration**

### **Custom Model Configurations**

For specialized use cases, you can configure different models for different tasks:

```bash
# High-quality analysis
LLM_MODEL="anthropic/claude-3-5-sonnet:beta"
LLM_MODEL_SETTINGS_TEMPERATURE="0.3"  # More focused

# Fast citation processing
CITATION_LLM_MODEL="openai/gpt-4o-mini"
CITATION_LLM_MODEL_SETTINGS_TEMPERATURE="0.1"  # Very focused

# Creative research agent
RESEARCH_AGENT_LLM_MODEL="anthropic/claude-3-5-sonnet:beta"
RESEARCH_AGENT_LLM_MODEL_SETTINGS_TEMPERATURE="0.7"  # More creative
```

### **Performance Optimization**

```bash
# For large document processing
LLM_CHUNK_SIZE="8000"                  # Larger chunks
LLM_MAP_REDUCE_THRESHOLD_MULTIPLIER="2.0"  # Earlier map-reduce

# For fast interactive use
RAG_RETRIEVAL_K="2"                    # Fewer documents
RAG_QA_MAX_TOKENS="1000"               # Shorter responses

# For batch processing
CITATION_CITATION_BATCH_SIZE="20"       # Larger batches
RAG_EMBEDDING_BATCH_SIZE="200"          # Efficient embedding
```

### **Security Configuration**

```bash
# Restrict API access
ENDPOINT_HOST="127.0.0.1"              # Localhost only

# Enable rate limiting
MODEL_USE_RATE_LIMITER="True"          # Prevent API abuse

# Secure logs
LOG_LEVEL="WARNING"                    # Minimal logging
LOG_FILE_LEVEL="ERROR"                 # Only errors to file
```

---

This configuration guide provides comprehensive coverage of all Thoth configuration options. Start with the quick setup checklist, then customize based on your specific needs and deployment scenario.
