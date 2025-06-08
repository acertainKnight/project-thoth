# Thoth Complete Feature Reference

This document provides a comprehensive reference of all features, commands, and capabilities available in the Thoth Research Assistant system.

## 🎯 **Command Line Interface**

Thoth provides a rich CLI interface accessible via `python -m thoth` or `thoth` (if installed globally).

### **Core Processing Commands**

#### **PDF Processing**
```bash
# Process a single PDF file
thoth process --pdf-path /path/to/paper.pdf

# Monitor directory for new PDFs
thoth monitor --watch-dir /path/to/pdfs --recursive --api-server

# Reprocess existing article note
thoth reprocess-note --article-id "10.1234/example.doi"

# Regenerate all notes
thoth regenerate-all-notes
```

#### **API Server**
```bash
# Start API server for Obsidian integration
thoth api --host 127.0.0.1 --port 8000 --reload

# Production server
thoth api --host 0.0.0.0 --port 8000
```

### **Discovery System Commands**

#### **Source Management**
```bash
# List all discovery sources
thoth discovery list

# Show detailed source information
thoth discovery show --name "arxiv_ml"

# Create new discovery source
thoth discovery create --name "pubmed_ai" --type api --description "AI papers from PubMed" --config-file config.json

# Edit existing source
thoth discovery edit --name "arxiv_ml" --description "Updated description" --config-file new_config.json

# Delete discovery source
thoth discovery delete --name "old_source" --confirm
```

#### **Discovery Execution**
```bash
# Run discovery for all active sources
thoth discovery run

# Run specific source with limits
thoth discovery run --source "arxiv_ml" --max-articles 25

# Test filtering system
thoth filter-test --create-sample-queries
```

#### **Discovery Scheduling**
```bash
# Start discovery scheduler
thoth discovery scheduler start

# Check scheduler status
thoth discovery scheduler status

# Stop scheduler (Ctrl+C when running)
```

### **Knowledge Base (RAG) Commands**

#### **Index Management**
```bash
# Index all documents for search
thoth rag index

# Clear and rebuild index
thoth rag clear --confirm
thoth rag index

# View RAG system statistics
thoth rag stats
```

#### **Search and Query**
```bash
# Search knowledge base
thoth rag search --query "transformer architecture" --k 5 --filter-type note

# Ask questions about research
thoth rag ask --question "What are the main contributions of attention mechanisms?" --k 4
```

### **Tag Management Commands**

```bash
# Complete tag consolidation and suggestion
thoth consolidate-tags

# Only consolidate existing tags
thoth consolidate-tags-only

# Only suggest new tags
thoth suggest-tags
```

### **Agent Interface**

```bash
# Start interactive research agent
thoth agent
```

## 🔧 **Service Layer Architecture**

Thoth uses a service-oriented architecture with the following services:

### **Core Services**

#### **ProcessingService** (`processing_service.py`)
- **Purpose**: Coordinates PDF to note conversion pipeline
- **Key Methods**:
  - `process_pdf(pdf_path)` - Complete PDF processing workflow
  - `process_batch(pdf_paths)` - Batch processing multiple PDFs
  - `get_processing_stats()` - Processing statistics and status

#### **DiscoveryService** (`discovery_service.py`)
- **Purpose**: Manages article discovery sources and scheduling
- **Key Methods**:
  - `create_source(source_config)` - Create new discovery source
  - `run_discovery(source_name, max_articles)` - Execute discovery
  - `start_scheduler()` / `stop_scheduler()` - Manage automated discovery
  - `get_schedule_status()` - Scheduler and source status

#### **RAGService** (`rag_service.py`)
- **Purpose**: Vector search and question-answering over research collection
- **Key Methods**:
  - `index_documents()` - Index documents for search
  - `search(query, k, filter)` - Semantic search
  - `ask_question(question, k)` - Question answering with sources
  - `get_stats()` - RAG system statistics

#### **CitationService** (`citation_service.py`)
- **Purpose**: Citation extraction, processing, and graph management
- **Key Methods**:
  - `extract_citations(text)` - Extract citations from text
  - `enrich_citations(citations)` - Enhance with metadata
  - `build_citation_graph()` - Create citation relationships
  - `get_citation_stats()` - Citation processing statistics

#### **NoteService** (`note_service.py`)
- **Purpose**: Generate and manage Obsidian-compatible notes
- **Key Methods**:
  - `create_note(pdf_path, analysis, citations)` - Generate structured note
  - `regenerate_note(article_id)` - Regenerate existing note
  - `batch_regenerate()` - Regenerate all notes
  - `update_note_template()` - Update note formatting

#### **TagService** (`tag_service.py`)
- **Purpose**: Tag consolidation and intelligent tagging
- **Key Methods**:
  - `consolidate_tags()` - Consolidate similar tags
  - `suggest_tags(title, abstract)` - AI-powered tag suggestions
  - `get_tag_statistics()` - Tag usage analytics
  - `export_tag_vocabulary()` - Export canonical tag list

#### **QueryService** (`query_service.py`)
- **Purpose**: Research query management for filtering
- **Key Methods**:
  - `create_query(query_config)` - Create research interest
  - `evaluate_article(article, query)` - Evaluate article relevance
  - `list_queries()` - Show all research queries
  - `update_query(name, updates)` - Modify existing query

#### **ArticleService** (`article_service.py`)
- **Purpose**: Article metadata management and filtering
- **Key Methods**:
  - `filter_article(metadata)` - Evaluate article for download
  - `store_article(pdf_path, metadata)` - Store approved article
  - `get_article_stats()` - Article processing statistics
  - `batch_evaluate(articles)` - Process multiple articles

#### **LLMService** (`llm_service.py`)
- **Purpose**: Unified LLM access and processing
- **Key Methods**:
  - `analyze_content(text, prompt_template)` - Content analysis
  - `process_batch(texts, template)` - Batch LLM processing
  - `get_usage_stats()` - Token usage and costs
  - `test_connection()` - Verify LLM availability

#### **WebSearchService** (`web_search_service.py`)
- **Purpose**: Web search integration for research
- **Key Methods**:
  - `search(query, providers)` - Multi-provider web search
  - `get_paper_metadata(url)` - Extract paper information
  - `validate_search_providers()` - Check provider availability

### **Service Manager** (`service_manager.py`)
- **Purpose**: Unified access point for all services
- **Usage**: `pipeline.services.discovery.run_discovery()`
- **Benefits**: Dependency injection, lazy loading, consistent interfaces

## 🤖 **Modern Agent System (LangGraph)**

### **Agent Tools Available**

#### **Discovery Tools** (`discovery_tools.py`)
- `list_discovery_sources` - Show all configured sources
- `create_arxiv_source` - Create ArXiv discovery source
- `create_pubmed_source` - Create PubMed discovery source
- `run_discovery` - Execute discovery for sources
- `delete_discovery_source` - Remove discovery source

#### **Query Tools** (`query_tools.py`)
- `list_queries` - Show all research queries
- `create_query` - Create new research interest
- `get_query` - Get detailed query information
- `edit_query` - Modify existing query
- `delete_query` - Remove research query

#### **RAG Tools** (`rag_tools.py`)
- `search_knowledge` - Search papers and notes
- `ask_knowledge` - Ask questions about research
- `index_knowledge` - Index documents for search
- `explain_connections` - Find paper relationships
- `rag_stats` - Show RAG system statistics

#### **Analysis Tools** (`analysis_tools.py`)
- `evaluate_article` - Evaluate article relevance
- `analyze_topic` - Analyze research topics
- `find_related` - Find related papers
- `get_citation_stats` - Citation network analysis
- `summarize_research` - Generate research summaries

#### **Web Tools** (`web_tools.py`)
- `web_search` - Search the web for research
- `extract_paper_info` - Get paper metadata from URLs

### **Agent Capabilities**
- **Natural Language Interface**: Conversational research assistance
- **Tool Selection**: Automatic selection of appropriate tools
- **Memory Management**: Persistent conversation history
- **Error Recovery**: Graceful handling of failures
- **Multi-turn Conversations**: Complex research workflows

## 🔍 **Discovery System Features**

### **Source Types**

#### **API Sources**
- **ArXiv**: Academic papers from ArXiv.org
  - Categories: cs.LG, cs.AI, cs.CL, cs.CV, etc.
  - Keywords, date ranges, sorting options
- **PubMed**: Medical and life science papers
  - MeSH terms, authors, journals
  - Publication types, date filtering

#### **Web Scraping Sources**
- **CSS Selector-based**: Extract data using CSS selectors
- **Navigation Rules**: Handle pagination and dynamic content
- **Rate Limiting**: Respectful scraping with delays
- **Error Recovery**: Robust handling of site changes

#### **Browser Emulator Sources**
- **Recorded Sessions**: Record login and navigation
- **Cookie Management**: Persist authentication
- **JavaScript Support**: Handle dynamic websites
- **Custom Actions**: Complex interaction workflows

### **Scheduling Features**
- **Flexible Intervals**: Minutes, hours, days, weeks
- **Time-of-Day Scheduling**: Run at specific times
- **Day-of-Week Filtering**: Weekdays only, specific days
- **Conditional Execution**: Skip runs based on conditions
- **Parallel Execution**: Multiple sources simultaneously

### **Chrome Extension Integration**
- **Point-and-Click Configuration**: Visual selector creation
- **Real-time Testing**: Test selectors on live pages
- **Configuration Export**: Save scraper configurations
- **Preview Mode**: See extracted data before saving

## 📊 **RAG (Knowledge Base) Features**

### **Document Types Supported**
- **Research Papers**: Full-text PDF content
- **Obsidian Notes**: Structured research notes
- **Markdown Files**: General markdown documents
- **Citations**: Reference metadata and abstracts

### **Search Capabilities**
- **Semantic Search**: Vector similarity search
- **Keyword Search**: Traditional text matching
- **Filtered Search**: By document type, date, tags
- **Hybrid Search**: Combine semantic and keyword

### **Question Answering**
- **Contextual Answers**: Based on relevant documents
- **Source Attribution**: Shows supporting documents
- **Multi-document Synthesis**: Combine information from multiple papers
- **Follow-up Questions**: Conversation-aware responses

### **Embedding Models Supported**
- OpenAI Text Embedding 3 (Small/Large)
- Custom embedding models via OpenRouter
- Configurable batch sizes and chunking strategies

## 🏷️ **Tag Management Features**

### **Tag Consolidation**
- **Similarity Detection**: Find related tags (#ml, #machine_learning)
- **Canonical Mapping**: Create authoritative tag names
- **Batch Updates**: Apply consolidation across all articles
- **Reasoning Reports**: Explain consolidation decisions

### **Tag Suggestion**
- **Content-Based**: Analyze titles and abstracts
- **Vocabulary-Aware**: Only suggest existing tags
- **Relevance Scoring**: Prioritize highly relevant tags
- **Batch Processing**: Handle large article collections

### **Tag Analytics**
- **Usage Statistics**: Most common tags and trends
- **Co-occurrence Analysis**: Related tag patterns
- **Coverage Reports**: Articles with/without tags
- **Quality Metrics**: Tag consistency and accuracy

## 📝 **Note Generation Features**

### **Template System**
- **Jinja2 Templates**: Flexible note formatting
- **Multiple Formats**: Research notes, summaries, citations
- **Custom Fields**: Configurable metadata inclusion
- **Styling Options**: Markdown formatting and structure

### **Content Sections**
- **Article Metadata**: Title, authors, publication info
- **Key Findings**: LLM-extracted insights
- **Methodology**: Research methods and approaches
- **Citations**: Referenced works with links
- **Tags**: Relevant topic tags
- **Personal Notes**: Space for user annotations

### **Link Generation**
- **PDF Links**: Direct access to source documents
- **Citation Links**: Cross-references between papers
- **Web Links**: External resources and URLs
- **Graph Links**: Citation network visualization

## 🔧 **Configuration System**

### **Configuration Categories**

#### **API Keys** (`API_*`)
- Mistral, OpenRouter, OpenAI, Anthropic
- OpenCitations, Semantic Scholar
- Google Search, Web Search providers

#### **LLM Configuration** (`LLM_*`)
- Model selection and parameters
- Context length and token limits
- Processing strategies (direct, refine, map-reduce)
- Specialized models for different tasks

#### **Directory Structure**
- PDF storage, markdown conversion
- Obsidian notes, templates
- Knowledge base, discovery results
- Logs and temporary files

#### **Service Configuration**
- API server host/port settings
- Monitor intervals and batch sizes
- Discovery scheduling and limits
- RAG embedding and search parameters

### **Environment Management**
- `.env` file support with examples
- Docker environment variables
- Development vs. production configs
- Encrypted API key storage

## 🐳 **Docker Support**

### **Container Configurations**
- **Production**: Optimized for deployment
- **Development**: Hot reload and debugging
- **Testing**: Isolated test environment

### **Volume Management**
- **Persistent Data**: Knowledge base and configurations
- **Host Integration**: Access to local files
- **Backup Support**: Easy data export/import

### **Networking**
- **Port Mapping**: API server access
- **Service Discovery**: Container communication
- **External Access**: Remote Obsidian connection

## 🔗 **Integration Features**

### **Obsidian Plugin**
- **Real-time Chat**: Interactive research assistant
- **Command Integration**: Quick research actions
- **Status Monitoring**: Connection and agent status
- **Remote Management**: WSL and Docker support

### **API Endpoints**
- **Research Chat**: Conversational interface
- **PDF Processing**: Document upload and processing
- **Knowledge Search**: Vector search and QA
- **Discovery Management**: Source configuration
- **Agent Control**: Start, stop, restart agent

### **External Services**
- **OpenCitations**: Citation metadata
- **Semantic Scholar**: Paper information
- **ArXiv/PubMed**: Paper discovery
- **Web Search**: General research queries

## 📈 **Monitoring and Analytics**

### **Processing Statistics**
- **PDF Conversion**: Success rates and errors
- **LLM Usage**: Token consumption and costs
- **Discovery Results**: Articles found and filtered
- **Knowledge Base**: Document counts and coverage

### **Performance Metrics**
- **Processing Speed**: Papers per hour/day
- **Search Performance**: Query response times
- **Agent Efficiency**: Tool usage and success rates
- **Resource Usage**: Memory, disk, network

### **Error Tracking**
- **Processing Failures**: PDF and conversion errors
- **API Failures**: Service timeouts and rate limits
- **Discovery Issues**: Scraping and network problems
- **Agent Errors**: Tool failures and recovery

## 🛠️ **Development Features**

### **Testing Framework**
- **Unit Tests**: Component-level testing
- **Integration Tests**: End-to-end workflows
- **Mock Services**: Isolated testing environments
- **Coverage Reports**: Code coverage analysis

### **Development Tools**
- **Hot Reload**: Live code updates
- **Debug Logging**: Detailed operation logs
- **Configuration Validation**: Settings verification
- **Performance Profiling**: Bottleneck identification

### **Extension Points**
- **Custom Tools**: Add new agent capabilities
- **Discovery Sources**: Integrate new data sources
- **Note Templates**: Create custom formats
- **Processing Plugins**: Custom analysis workflows

## 🚀 **Deployment Options**

### **Local Installation**
- **Python Environment**: Direct installation
- **Virtual Environments**: Isolated dependencies
- **System Integration**: OS-level services

### **Docker Deployment**
- **Single Container**: All-in-one deployment
- **Multi-container**: Scalable architecture
- **Cloud Deployment**: AWS, GCP, Azure

### **Development Setup**
- **Local Development**: IDE integration
- **Remote Development**: Container-based
- **Collaborative Setup**: Shared configurations

This comprehensive reference covers all major features and capabilities of the Thoth Research Assistant system. Each component is designed to work together seamlessly while remaining modular and extensible.
