# 🔍 Discovery Automation & Recurring Searches

This guide explains how Thoth's **automated discovery system** works with recurring searches, background processing, and multi-service coordination.

## 🏗️ Discovery Service Architecture

The discovery system runs as **automated background processes** that continuously find new research papers:

```
┌─────────────────────────────────────────────────────────────┐
│                Discovery Service Ecosystem                  │
├─────────────────────────────────────────────────────────────┤
│ 🕐 Scheduler Service    │ 🔍 Discovery Sources              │
│   - Cron-like timing    │   - ArXiv API                    │
│   - Background threads  │   - PubMed API                   │
│   - State persistence   │   - Semantic Scholar             │
│   - Error recovery      │   - CrossRef API                 │
├─────────────────────────────────────────────────────────────┤
│ 🤖 Auto-Discovery      │ 📊 Results Processing            │
│   - Context analysis    │   - Quality filtering            │
│   - Smart suggestions   │   - Duplicate detection          │
│   - Source creation     │   - PDF download                 │
│   - User preferences    │   - Content analysis             │
└─────────────────────────────────────────────────────────────┘
```

## 🕐 Recurring Discovery Scheduler

### How the Scheduler Works

The discovery scheduler runs as a **background daemon thread** that:

1. **Monitors discovery sources** every minute
2. **Checks scheduled run times** for each source
3. **Executes discovery** when sources are due
4. **Processes found papers** through filtering
5. **Updates schedules** for next runs

```python
# Example: ArXiv source runs every 6 hours
{
    "name": "arxiv_transformers",
    "schedule": {
        "interval_minutes": 360,  # 6 hours
        "max_articles_per_run": 50,
        "enabled": True
    },
    "last_run": "2024-01-15T10:30:00Z",
    "next_run": "2024-01-15T16:30:00Z"
}
```

### Scheduler Deployment Options

#### **Option 1: Integrated with Main Service (Default)**
```bash
# Scheduler runs inside the main chat service
docker-compose up -d thoth-app
# Discovery scheduler automatically starts as background thread
```

#### **Option 2: Standalone Discovery Service**
```bash
# Run discovery as separate service
docker-compose -f deployment/docker-compose.services.yml up -d thoth-discovery

# Or via CLI
python -m thoth discovery server
```

#### **Option 3: External Cron-based**
```bash
# Use system cron for discovery
# Add to crontab:
0 */6 * * * /usr/bin/docker exec thoth-app python -m thoth discovery run
```

## 🔄 Automated Discovery Sources

### Source Types and Scheduling

#### **1. Academic API Sources**

**ArXiv Sources** (Preprint papers)
```bash
# Create recurring ArXiv source
python -m thoth discovery create \
  --name "arxiv_ml_papers" \
  --type "api" \
  --description "Machine learning papers from ArXiv"

# Configuration automatically includes:
{
  "api_config": {
    "source": "arxiv",
    "categories": ["cs.LG", "cs.AI", "cs.CL"],
    "keywords": ["machine learning", "neural networks"],
    "sort_by": "lastUpdatedDate"
  },
  "schedule_config": {
    "interval_minutes": 360,     # Every 6 hours
    "max_articles_per_run": 50,
    "enabled": True,
    "time_of_day": "09:00",     # Preferred run time
    "days_of_week": [1,2,3,4,5] # Weekdays only
  }
}
```

**PubMed Sources** (Biomedical papers)
```bash
# Create PubMed source
python -m thoth discovery create \
  --name "pubmed_ai_health" \
  --type "api" \
  --config-file pubmed_config.json

# Runs every 12 hours, finds biomedical AI papers
```

**Semantic Scholar Sources** (Peer-reviewed papers)
```bash
# Broad academic search
python -m thoth discovery create \
  --name "semantic_scholar_broad" \
  --type "api"

# Runs daily, searches across all academic disciplines
```

#### **2. Web Scraping Sources**

**Journal RSS Feeds**
```bash
# Monitor journal RSS feeds
{
  "name": "nature_ai_feed",
  "source_type": "scraper",
  "scraper_config": {
    "base_url": "https://www.nature.com/subjects/machine-learning.rss",
    "extraction_rules": {...}
  },
  "schedule_config": {
    "interval_minutes": 180,  # Every 3 hours
    "enabled": True
  }
}
```

**Conference Proceedings**
```bash
# Monitor conference websites
{
  "name": "neurips_proceedings",
  "source_type": "scraper",
  "schedule_config": {
    "interval_minutes": 1440,  # Daily
    "time_of_day": "08:00"
  }
}
```

### 📋 Managing Discovery Sources

#### **List All Sources and Their Schedules**
```bash
# Via CLI
python -m thoth discovery list

# Via agent
python -m thoth agent
# In chat: "Show me my discovery sources and their schedules"

# Via MCP tool
# Agent automatically uses: list_discovery_sources
```

#### **Create Scheduled Sources**
```bash
# Interactive creation
python -m thoth discovery create

# Programmatic creation
python -m thoth discovery create \
  --name "custom_source" \
  --type "api" \
  --description "Custom research source" \
  --config-file source_config.json
```

#### **Monitor Discovery Activity**
```bash
# Check scheduler status
python -m thoth discovery scheduler status

# View recent discovery results
python -m thoth discovery results --last 24h

# Monitor in real-time
python -m thoth discovery monitor
```

## 🤖 Auto-Discovery System

### Context-Aware Discovery

The system **automatically suggests new discovery sources** based on your conversations:

```python
# When you chat about research topics:
"I'm interested in quantum machine learning applications"

# Auto-discovery system:
1. Analyzes conversation context
2. Identifies research topics: ["quantum computing", "machine learning"]
3. Suggests relevant sources:
   - ArXiv categories: ["quant-ph", "cs.LG"]
   - PubMed terms: ["quantum machine learning"]
   - Keywords: ["quantum neural networks", "variational quantum"]
4. Optionally auto-creates sources (if confidence > 80%)
```

### Auto-Discovery Configuration

```bash
# Enable auto-discovery in .env
THOTH_AUTO_DISCOVERY_ENABLED=true
THOTH_AUTO_DISCOVERY_CONFIDENCE_THRESHOLD=0.8
THOTH_AUTO_DISCOVERY_MAX_SOURCES_PER_SESSION=3

# Auto-discovery runs:
# - After every 5 conversation turns
# - When research topics are mentioned
# - During idle periods (background analysis)
```

## 📊 Multi-Service Discovery Deployment

### Service Distribution Options

#### **Option 1: Integrated Discovery (Default)**
```yaml
# Discovery runs inside main chat service
thoth-chat-service:
  environment:
    THOTH_DISCOVERY_AUTO_START_SCHEDULER: "true"
    THOTH_DISCOVERY_DEFAULT_MAX_ARTICLES: 50
  # Discovery scheduler starts automatically
```

#### **Option 2: Dedicated Discovery Service**
```yaml
# Separate discovery service
thoth-discovery-service:
  environment:
    THOTH_SERVICE_MODE: discovery_only
    THOTH_DISCOVERY_SCHEDULER_ENABLED: "true"
  # Runs only discovery and scheduling
```

#### **Option 3: Distributed Discovery**
```yaml
# Multiple discovery workers
thoth-discovery-worker-1:
  environment:
    THOTH_DISCOVERY_WORKER_ID: "worker_1"
    THOTH_DISCOVERY_SOURCES: "arxiv,semantic_scholar"

thoth-discovery-worker-2:
  environment:
    THOTH_DISCOVERY_WORKER_ID: "worker_2"
    THOTH_DISCOVERY_SOURCES: "pubmed,crossref"
```

### 🔄 Background Processing Pipeline

Each discovery source runs this automated pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                Discovery Processing Pipeline                 │
├─────────────────────────────────────────────────────────────┤
│ 1. ⏰ Scheduler Triggers   │ 2. 🔍 Source Execution        │
│   - Check run schedule     │   - Query external APIs       │
│   - Validate source config │   - Parse search results      │
│   - Start discovery task   │   - Extract metadata          │
├─────────────────────────────────────────────────────────────┤
│ 3. 🔬 Quality Filtering    │ 4. 💾 Data Processing         │
│   - Query-based filtering  │   - Download PDFs             │
│   - Relevance scoring      │   - Extract content           │
│   - Duplicate detection    │   - Generate embeddings       │
├─────────────────────────────────────────────────────────────┤
│ 5. 🧠 Memory Integration   │ 6. 📈 Results Tracking        │
│   - Store in knowledge base│   - Update source statistics  │
│   - Update citation graph  │   - Log discovery results     │
│   - Trigger notifications  │   - Schedule next run         │
└─────────────────────────────────────────────────────────────┘
```

## 🎛️ Discovery Service Management

### Starting Discovery Services

#### **Method 1: Integrated (Recommended)**
```bash
# Discovery starts automatically with main service
./scripts/start-all-services.sh dev

# Discovery scheduler runs in background
# Check status:
python -m thoth discovery scheduler status
```

#### **Method 2: Standalone Discovery Service**
```bash
# Start dedicated discovery service
make -f Makefile.services start-discovery

# Or manually:
python -m thoth discovery server

# This runs:
# - Discovery scheduler (background thread)
# - Source management API
# - Results processing pipeline
```

#### **Method 3: External Discovery Workers**
```bash
# Start multiple discovery workers
docker-compose -f deployment/docker-compose.services.yml up -d \
  --scale thoth-discovery=3

# Each worker handles different sources
# Load balanced across workers
```

### Monitoring Discovery Activity

#### **Real-Time Monitoring**
```bash
# Monitor discovery activity
python -m thoth discovery monitor

# View live discovery logs
make -f Makefile.services logs-discovery

# Check discovery service health
curl http://localhost:8002/health  # If running standalone
```

#### **Discovery Dashboard**
```bash
# Via agent
python -m thoth agent
# In chat: "Show me discovery activity and recent findings"

# Via web interface (if monitoring enabled)
# Grafana dashboard: http://localhost:3000
# - Discovery source activity
# - Papers found per hour/day
# - Success/failure rates
# - Source performance metrics
```

## 📅 Discovery Scheduling Examples

### Example 1: Academic Research Pipeline
```bash
# Set up comprehensive discovery for ML research
python -m thoth discovery create --name "arxiv_ml_daily" \
  --type "api" --schedule "daily" --time "09:00"

python -m thoth discovery create --name "semantic_scholar_weekly" \
  --type "api" --schedule "weekly" --day "monday"

python -m thoth discovery create --name "pubmed_ai_health" \
  --type "api" --schedule "12h"

# Results in:
# - 50 ArXiv papers daily at 9 AM
# - 100 Semantic Scholar papers weekly on Monday
# - 30 PubMed papers every 12 hours
# - All automatically filtered and processed
```

### Example 2: Specialized Research Monitoring
```bash
# Monitor specific research areas
{
  "sources": [
    {
      "name": "quantum_ml_arxiv",
      "schedule": "6h",
      "keywords": ["quantum machine learning", "variational quantum"],
      "categories": ["quant-ph", "cs.LG"]
    },
    {
      "name": "transformer_efficiency",
      "schedule": "daily",
      "keywords": ["efficient transformers", "sparse attention"],
      "venues": ["ICLR", "NeurIPS", "ICML"]
    }
  ]
}
```

## 🔧 Service Configuration for Discovery

### Environment Configuration

#### **Main Application (.env)**
```bash
# Discovery service integration
THOTH_DISCOVERY_AUTO_START_SCHEDULER=true
THOTH_DISCOVERY_DEFAULT_MAX_ARTICLES=50
THOTH_DISCOVERY_DEFAULT_INTERVAL_MINUTES=360

# Memory integration for discovery
LETTA_SERVER_URL=http://localhost:8283
THOTH_CHROMADB_URL=http://localhost:8003

# Auto-discovery features
THOTH_AUTO_DISCOVERY_ENABLED=true
THOTH_AUTO_DISCOVERY_CONFIDENCE_THRESHOLD=0.8
```

#### **Discovery Service (.env.discovery)**
```bash
# If running standalone discovery service
DISCOVERY_SERVICE_MODE=standalone
DISCOVERY_SCHEDULER_ENABLED=true
DISCOVERY_MAX_CONCURRENT_SOURCES=5
DISCOVERY_RESULTS_RETENTION_DAYS=30

# External service connections
THOTH_MAIN_API_URL=http://localhost:8000
LETTA_MEMORY_URL=http://localhost:8283
CHROMADB_URL=http://localhost:8003
```

### 📊 Discovery Service Monitoring

#### **Scheduler Status**
```bash
# Check what's scheduled to run
python -m thoth discovery scheduler status

# Example output:
{
  "running": true,
  "total_sources": 5,
  "enabled_sources": 4,
  "next_runs": [
    {
      "source": "arxiv_ml_daily",
      "next_run": "2024-01-16T09:00:00Z",
      "time_until": "2h 30m"
    },
    {
      "source": "pubmed_ai_health",
      "next_run": "2024-01-15T22:00:00Z",
      "time_until": "15m"
    }
  ]
}
```

#### **Discovery Metrics**
```bash
# View discovery performance
python -m thoth discovery stats --days 7

# Results:
{
  "total_runs": 42,
  "papers_found": 1,247,
  "papers_downloaded": 892,
  "success_rate": 0.94,
  "avg_papers_per_run": 29.7,
  "sources": {
    "arxiv_ml_daily": {
      "runs": 7,
      "papers_found": 350,
      "success_rate": 0.98
    },
    "semantic_scholar_weekly": {
      "runs": 1,
      "papers_found": 127,
      "success_rate": 0.89
    }
  }
}
```

## 🚀 Starting Discovery Services

### Multi-Service Discovery Setup

#### **1. Full Discovery Stack**
```bash
# Start all services including discovery
./scripts/start-all-services.sh dev

# This includes:
# - Memory service (for storing discovery context)
# - Chat service (with integrated discovery scheduler)
# - Vector database (for paper storage)
# - Monitoring (for discovery metrics)
```

#### **2. Discovery-Only Services**
```bash
# Start just discovery components
make -f Makefile.services start-memory     # For context storage
make -f Makefile.services start-vector-db  # For paper storage
make -f Makefile.services start-discovery  # Discovery service

# Or all at once:
make -f Makefile.services start-core       # Memory + Vector DB
python -m thoth discovery server           # Discovery service
```

#### **3. Distributed Discovery**
```bash
# Start multiple discovery workers
docker-compose -f deployment/docker-compose.services.yml up -d \
  --scale thoth-discovery=3

# Each worker handles different sources:
# Worker 1: ArXiv + Semantic Scholar
# Worker 2: PubMed + CrossRef
# Worker 3: Web scraping + RSS feeds
```

### Verifying Discovery is Running

```bash
# Check discovery scheduler status
python -m thoth discovery scheduler status

# Check recent discovery activity
python -m thoth discovery results --recent

# Monitor discovery logs
make -f Makefile.services logs-discovery

# Test discovery manually
python -m thoth discovery run --source "arxiv_ml_papers"
```

## 🤖 Auto-Discovery Integration

### Conversation-Driven Discovery

The auto-discovery system **analyzes your research conversations** and automatically creates discovery sources:

```python
# Example conversation:
User: "I'm researching quantum error correction in NISQ devices"

# Auto-discovery system:
1. Analyzes conversation: "quantum error correction", "NISQ devices"
2. Identifies research domains: ["quantum computing", "error correction"]
3. Suggests discovery sources:
   - ArXiv categories: ["quant-ph", "cs.ET"]
   - Keywords: ["quantum error correction", "NISQ", "noise mitigation"]
4. Creates source: "quantum_error_correction_auto"
5. Schedules: Every 8 hours, max 30 papers

# Agent response:
"I've created an auto-discovery source for quantum error correction research.
It will check ArXiv every 8 hours for new papers on NISQ devices and error correction."
```

### Auto-Discovery Configuration

```bash
# In your agent conversation:
"Enable auto-discovery for my research interests"

# Or via environment:
THOTH_AUTO_DISCOVERY_ENABLED=true
THOTH_AUTO_DISCOVERY_ANALYSIS_WINDOW=24h
THOTH_AUTO_DISCOVERY_MIN_CONFIDENCE=0.7
THOTH_AUTO_DISCOVERY_MAX_SOURCES_PER_TOPIC=2
```

## 🔄 Discovery Service Orchestration

### Service Coordination

Discovery services coordinate with other Thoth services:

```
Discovery Service ←→ Memory Service (Letta)
    ↓ stores research context and preferences

Discovery Service ←→ Chat Agent Service
    ↓ receives auto-discovery triggers

Discovery Service ←→ Vector Database
    ↓ stores discovered papers for RAG

Discovery Service ←→ Monitoring Stack
    ↓ reports metrics and health status
```

### Cross-Service Communication

```python
# Discovery finds new papers → Stores in memory
memory_manager.archival_memory_insert(
    content=f"Found {len(papers)} new papers on {topic}",
    metadata={"source": source_name, "timestamp": datetime.now()}
)

# Discovery updates → Triggers RAG reindexing
rag_service.index_new_documents(discovered_papers)

# Discovery metrics → Updates monitoring
prometheus_metrics.discovery_papers_found.inc(len(papers))
```

## 📈 Production Discovery Scaling

### High-Volume Discovery

#### **Scaling Strategy**
```bash
# Scale discovery workers based on source count
docker-compose up -d --scale thoth-discovery=5

# Distribute sources across workers:
# Worker 1: ArXiv sources (high volume)
# Worker 2: PubMed sources (medical focus)
# Worker 3: Semantic Scholar (broad academic)
# Worker 4: Web scraping (conference sites)
# Worker 5: RSS feeds (journal updates)
```

#### **Load Balancing**
```yaml
# nginx load balancer for discovery API
upstream discovery_backend {
    least_conn;
    server thoth-discovery-1:8002;
    server thoth-discovery-2:8002;
    server thoth-discovery-3:8002;
}
```

### Performance Optimization

#### **Caching Strategy**
```bash
# Discovery results caching
DISCOVERY_CACHE_TTL=3600              # 1 hour cache
DISCOVERY_DUPLICATE_DETECTION=true    # Skip known papers
DISCOVERY_RATE_LIMIT_DELAY=1.0       # API rate limiting
```

#### **Resource Limits**
```yaml
# Discovery service resources
thoth-discovery:
  deploy:
    resources:
      limits:
        memory: 2G      # For processing many papers
        cpus: '1.0'     # CPU for text processing
      reservations:
        memory: 512M
        cpus: '0.5'
```

## 🛠️ Discovery Management Commands

### Daily Operations

```bash
# Check what's running
./scripts/start-all-services.sh status

# View discovery activity
python -m thoth discovery scheduler status
python -m thoth discovery results --today

# Manual discovery run
python -m thoth discovery run --source "arxiv_ml_papers"
```

### Maintenance Operations

```bash
# Update discovery sources
python -m thoth discovery edit --name "source_name" --config-file new_config.json

# Backup discovery configuration
make -f Makefile.services backup-all

# Clean old discovery results
python -m thoth discovery cleanup --older-than 30d
```

### Troubleshooting Discovery

```bash
# Check discovery service health
curl http://localhost:8002/health  # If standalone
make -f Makefile.services logs-discovery

# Test individual sources
python -m thoth discovery test --source "arxiv_ml_papers"

# Reset discovery scheduler
python -m thoth discovery scheduler restart
```

## 🎉 **Discovery Services are Fully Automated!**

Your discovery system provides:

- ✅ **Automated recurring searches** every few hours/days
- ✅ **Background processing** in separate containers/threads
- ✅ **Multi-source coordination** (ArXiv, PubMed, Semantic Scholar)
- ✅ **Context-aware auto-discovery** based on conversations
- ✅ **Independent scaling** of discovery workers
- ✅ **Persistent scheduling** across service restarts
- ✅ **Real-time monitoring** and metrics
- ✅ **Integration with memory system** for research context

The discovery system runs **continuously in the background**, finding new papers relevant to your research interests without any manual intervention!
