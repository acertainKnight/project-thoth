# Thoth Usage Guide

This guide covers the day-to-day usage of Thoth Research Assistant for research workflows, document processing, and knowledge management.

## Table of Contents

- [Getting Started](#getting-started)
- [Command Line Interface](#command-line-interface)
- [Obsidian Plugin Usage](#obsidian-plugin-usage)
- [Research Workflows](#research-workflows)
- [Document Processing](#document-processing)
- [Knowledge Management](#knowledge-management)
- [API Usage](#api-usage)
- [Advanced Features](#advanced-features)

## Getting Started

### Quick Start Workflow

1. **Start Thoth services**
   ```bash
   make deploy-plugin
   make start-api
   ```

2. **Open Obsidian and start a research chat**
   - Press `Ctrl/Cmd+P` → "Open Research Chat"
   - Or click the Thoth icon in the ribbon

3. **Begin your research**
   ```
   "Find recent papers on transformer architectures in NLP"
   ```

## Command Line Interface

### Core Commands

#### General Help
```bash
python -m thoth --help              # Show all commands
python -m thoth <command> --help    # Help for specific command
```

#### Agent Operations
```bash
# Start interactive research assistant with full tool access
python -m thoth agent
```

#### System Operations
```bash
# Start Obsidian API server
python -m thoth api --host 127.0.0.1 --port 8000

# Monitor PDF directory for processing
python -m thoth monitor --watch-dir ./papers --optimized

# Monitor with API server integration
python -m thoth monitor --watch-dir ./papers --api-server --optimized

# Locate specific PDF by title or DOI
python -m thoth locate-pdf "Attention Is All You Need"
```

#### Discovery Operations
```bash
# List all discovery sources
python -m thoth discovery list

# Run discovery for a specific source
python -m thoth discovery run --source "source_name" --max-articles 50

# Show details about a discovery source
python -m thoth discovery show --name "source_name"

# Create a new discovery source (interactive)
python -m thoth discovery create
```

#### RAG Operations
```bash
# Index documents for RAG search
python -m thoth rag index --force

# Search the knowledge base
python -m thoth rag search --query "attention mechanisms" --k 10

# Ask questions about the knowledge base
python -m thoth rag ask --question "What are the latest attention mechanisms?" --k 5

# Filter search by document type
python -m thoth rag search --query "transformers" --filter-type "markdown" --k 10
```

#### MCP Server
```bash
# Start MCP server for CLI integration
python -m thoth mcp stdio

# HTTP MCP server
python -m thoth mcp http --host localhost --port 8001

# SSE (Server-Sent Events) server
python -m thoth mcp sse --host localhost --port 8002
```

#### System Operations
```bash
# Check system status
python -m thoth system status

# Health check
python -m thoth system health

# Performance monitoring
python -m thoth performance monitor --duration 60

# Clear caches
python -m thoth system clean-cache
```

### CLI Examples

#### Research Workflow Example
```bash
# 1. Start the API server
python -m thoth api --host 127.0.0.1 --port 8000

# 2. Set up document monitoring
python -m thoth monitor --watch-dir ./papers --api-server --optimized

# 3. List and run discovery sources
python -m thoth discovery list
python -m thoth discovery run --source "arxiv_ml" --max-articles 30

# 4. Index documents for RAG
python -m thoth rag index --force

# 5. Search and query knowledge base
python -m thoth rag search --query "attention mechanisms" --k 10
python -m thoth rag ask --question "Compare different attention mechanisms in transformers"

# 6. Interactive research session
python -m thoth agent
```

## Obsidian Plugin Usage

### Main Interface

#### Ribbon Icon
- Click the Thoth message icon to open the main chat interface
- Right-click for quick actions menu

#### Command Palette Integration
Access Thoth commands via `Ctrl/Cmd+P`:
- **Open Research Chat** - Main chat interface
- **Start Thoth Agent** - Start background services
- **Stop Thoth Agent** - Stop background services
- **Restart Thoth Agent** - Restart services
- **Insert Research Query** - Process selected text

### Chat Interface

#### Basic Chat Operations
1. **Start a conversation**
   - Type your research question
   - Press Enter or click Send
   - Wait for AI response

2. **Multi-turn conversations**
   - Ask follow-up questions
   - Reference previous responses
   - Build on earlier research

3. **Document references**
   - Ask about specific papers: "Tell me about the paper 'Attention Is All You Need'"
   - Query your document collection: "What papers do I have about neural networks?"

#### Advanced Chat Features

##### Multi-Chat Windows
- Open multiple research conversations simultaneously
- Switch between different research topics
- Each chat maintains independent context

##### Chat Session Management
- **Save sessions**: Conversations are automatically saved
- **Load previous sessions**: Access chat history from settings
- **Export conversations**: Save chat logs as Markdown files

##### Special Commands
```
/help                    # Show available commands
/clear                   # Clear current conversation
/export                  # Export chat to file
/settings               # Open plugin settings
/status                 # Show system status
```

### Settings Configuration

#### API Configuration
- **Primary LLM Model**: Choose your preferred language model
- **Analysis Model**: Specialized model for document analysis
- **Temperature**: Control response creativity (0.0-1.0)
- **Max Tokens**: Set response length limits

#### Directory Settings
- **Workspace Directory**: Main working directory
- **PDF Directory**: Where PDFs are stored and monitored
- **Data Directory**: Database and cache location
- **Logs Directory**: Log file location

#### Behavior Settings
- **Auto-start Agent**: Start services when Obsidian loads
- **Show Status Bar**: Display connection status
- **Enable Notifications**: Show processing notifications
- **Chat History Limit**: Number of messages to retain

## Research Workflows

### Academic Paper Analysis

#### 1. Paper Discovery
```bash
# Discover papers by topic
python -m thoth discovery start --query "neural architecture search" --max-articles 25

# Discover from specific venues
python -m thoth discovery arxiv --query "transformers" --date-range "2023-01-01,2024-01-01"
```

#### 2. Document Processing
```bash
# Process discovered papers
python -m thoth pdf process --input-dir ./data/pdfs --extract-citations --extract-metadata
```

#### 3. Analysis and Summarization
Via Obsidian chat:
```
"Analyze the papers in my collection about attention mechanisms and provide:
1. Key innovations in each paper
2. Common themes and trends
3. Gaps in current research
4. Potential future directions"
```

#### 4. Citation Analysis
```bash
# Extract and analyze citations
python -m thoth citations analyze --input-dir ./processed-papers

# Build citation network
python -m thoth knowledge build --focus citations
```

### Literature Review Workflow

#### Step 1: Define Research Scope
```
Via Obsidian: "Help me plan a literature review on 'multimodal learning in computer vision'. What key topics should I cover?"
```

#### Step 2: Systematic Discovery
```bash
# Comprehensive search across sources
python -m thoth discovery start --query "multimodal learning computer vision" --max-articles 100
python -m thoth discovery start --query "vision-language models" --max-articles 50
python -m thoth discovery start --query "cross-modal attention" --max-articles 30
```

#### Step 3: Document Organization
```bash
# Process and categorize papers
python -m thoth pdf process --input-dir ./literature-review-pdfs --extract-all
python -m thoth tags auto-tag --source-dir ./processed-papers
```

#### Step 4: Synthesis and Writing
Via Obsidian:
```
"Based on my paper collection, create a structured outline for a literature review on multimodal learning, including:
- Historical development
- Current approaches
- Key challenges
- Future directions"
```

### Comparative Analysis

#### Compare Methodologies
```
"Compare the attention mechanisms used in these papers: [list specific papers or ask Thoth to identify relevant papers]"
```

#### Trend Analysis
```
"Analyze the evolution of transformer architectures from 2017 to 2024 based on my paper collection"
```

#### Gap Analysis
```
"Identify research gaps in current work on federated learning based on the papers I've collected"
```

## Document Processing

### PDF Processing Options

#### Basic Processing
```bash
# Simple PDF processing
python -m thoth pdf process --file research-paper.pdf
```

#### Advanced Processing
```bash
# Full extraction with metadata
python -m thoth pdf process \
  --file research-paper.pdf \
  --extract-citations \
  --extract-metadata \
  --extract-figures \
  --ocr-images
```

#### Batch Processing
```bash
# Process entire directory
python -m thoth pdf process \
  --input-dir ./research-papers \
  --output-dir ./processed \
  --parallel 4 \
  --extract-all
```

### Document Monitoring

#### Real-time Processing
```bash
# Monitor directory for new PDFs
python -m thoth pdf monitor --directory ./incoming-papers --auto-process
```

#### Scheduled Processing
```bash
# Schedule periodic processing
python -m thoth pdf schedule --directory ./papers --interval 3600  # Every hour
```

### Text Extraction and Analysis

#### Content Extraction
- **Main text**: Article body and abstract
- **Citations**: Bibliography and in-text references
- **Metadata**: Title, authors, publication info
- **Figures**: Captions and referenced images
- **Tables**: Structured data extraction

#### Quality Assessment
- **Confidence scores**: OCR and extraction quality
- **Completeness**: Missing sections identification
- **Language detection**: Multi-language support

## Knowledge Management

### Vector Database Operations

#### Building Knowledge Base
```bash
# Build from processed documents
python -m thoth rag build --source-dir ./processed-papers

# Incremental updates
python -m thoth rag update --new-documents ./new-papers

# Rebuild with different embedding model
python -m thoth rag rebuild --embedding-model sentence-transformers/all-mpnet-base-v2
```

#### Querying Knowledge Base
```bash
# Direct queries
python -m thoth rag query "What are the main challenges in federated learning?"

# Similarity search
python -m thoth rag similar --document "paper-id-123" --top-k 10

# Advanced queries with filters
python -m thoth rag query "transformer architecture" --filter "year:2023" --top-k 5
```

### Knowledge Graph Operations

#### Graph Construction
```bash
# Build knowledge graph
python -m thoth knowledge build --source-dir ./processed-papers

# Focus on specific relationships
python -m thoth knowledge build --focus citations,authors,concepts
```

#### Graph Querying
```bash
# Find related concepts
python -m thoth knowledge query --concept "attention mechanism" --relationship "related_to"

# Author networks
python -m thoth knowledge authors --name "Yoshua Bengio" --depth 2

# Citation paths
python -m thoth knowledge path --from "paper-1" --to "paper-2"
```

#### Graph Export
```bash
# Export for visualization
python -m thoth knowledge export --format graphml --output research-graph.graphml
python -m thoth knowledge export --format json --output research-data.json
```

### Tag Management

#### Automatic Tagging
```bash
# Auto-tag documents
python -m thoth tags auto-tag --source-dir ./processed-papers

# Custom tag models
python -m thoth tags train --training-data ./tagged-examples
```

#### Manual Tag Operations
```bash
# Add tags
python -m thoth tags add --document "paper-id" --tags "deep-learning,computer-vision"

# Query by tags
python -m thoth tags query --tags "machine-learning,nlp" --operator AND
```

## API Usage

### REST API Endpoints

#### Authentication
```python
import requests

# Most endpoints don't require authentication for local usage
base_url = "http://localhost:8000"
```

#### Chat Operations
```python
# Create chat session
response = requests.post(f"{base_url}/chat/sessions",
                        json={"title": "Research Session"})
session_id = response.json()["id"]

# Send message
response = requests.post(f"{base_url}/chat/sessions/{session_id}/messages",
                        json={"message": "Summarize recent ML papers"})
print(response.json()["response"])

# Get chat history
history = requests.get(f"{base_url}/chat/sessions/{session_id}/messages")
```

#### Document Operations
```python
# Upload document
with open("paper.pdf", "rb") as f:
    response = requests.post(f"{base_url}/documents/upload",
                           files={"file": f})

# Process document
doc_id = response.json()["document_id"]
processing = requests.post(f"{base_url}/documents/{doc_id}/process")

# Get processing status
status = requests.get(f"{base_url}/documents/{doc_id}/status")
```

#### Search and Query
```python
# Vector search
search_results = requests.post(f"{base_url}/search/vector",
                              json={"query": "attention mechanisms",
                                    "top_k": 10})

# Knowledge graph query
graph_results = requests.post(f"{base_url}/knowledge/query",
                             json={"concept": "neural networks",
                                   "max_depth": 2})
```

### WebSocket Integration

#### Real-time Chat
```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"AI: {data['response']}")

def on_open(ws):
    ws.send(json.dumps({
        "type": "chat",
        "message": "Hello, how can you help with my research?"
    }))

ws = websocket.WebSocketApp("ws://localhost:8000/ws/chat",
                           on_message=on_message,
                           on_open=on_open)
ws.run_forever()
```

#### Processing Updates
```python
# Monitor document processing
def on_processing_update(ws, message):
    data = json.loads(message)
    print(f"Processing: {data['status']} - {data['progress']}%")

ws = websocket.WebSocketApp("ws://localhost:8000/ws/processing",
                           on_message=on_processing_update)
```

## Advanced Features

### Custom Prompt Templates

#### Creating Templates
Create custom prompts in `./prompts/` directory:

```markdown
# analysis_template.md
Analyze the following research paper:

Title: {{title}}
Authors: {{authors}}
Abstract: {{abstract}}

Please provide:
1. Main contributions
2. Methodology summary
3. Key findings
4. Limitations
5. Future work suggestions
```

#### Using Templates
```bash
python -m thoth agent research --template analysis_template --document paper-id-123
```

### Plugin Development

#### Custom Discovery Plugins
```python
# src/thoth/discovery/plugins/custom_source.py
from thoth.discovery.plugins.base import DiscoveryPlugin

class CustomSourcePlugin(DiscoveryPlugin):
    def discover(self, query: str, max_results: int) -> List[Document]:
        # Implement custom discovery logic
        pass
```

#### Custom Processing Pipelines
```python
# src/thoth/pipelines/custom_pipeline.py
from thoth.pipelines.base import BasePipeline

class CustomPipeline(BasePipeline):
    def process_document(self, document: Document) -> ProcessedDocument:
        # Implement custom processing
        pass
```

### Integration with External Tools

#### Citation Managers
```bash
# Export to Zotero format
python -m thoth citations export --format zotero --output library.json

# Import from Mendeley
python -m thoth citations import --source mendeley --file library.bib
```

#### Version Control Integration
```bash
# Track research progress
git add .
git commit -m "Added analysis of transformer papers"

# Create research branches
git checkout -b literature-review-multimodal
```

#### Jupyter Notebook Integration
```python
# In Jupyter notebook
from thoth import ThothPipeline

pipeline = ThothPipeline()
results = pipeline.query("What are the latest developments in computer vision?")
```

## Performance Optimization

### Batch Processing
```bash
# Process multiple documents efficiently
python -m thoth pdf process --input-dir ./papers --batch-size 10 --parallel 4
```

### Caching Configuration
```bash
# Enable aggressive caching
export THOTH_CACHE_TTL=3600
export THOTH_ENABLE_CACHE=true

# Clear caches when needed
python -m thoth system clear-cache
```

### Memory Management
```bash
# For large document collections
export THOTH_MAX_MEMORY=16GB
export THOTH_CHUNK_SIZE=1024
export THOTH_MAX_CONCURRENT=2
```

## Troubleshooting Common Issues

### Performance Issues
- Reduce batch sizes
- Enable caching
- Use faster embedding models
- Increase system resources

### Processing Failures
- Check PDF quality and format
- Verify API key validity
- Monitor disk space
- Check log files

### Connection Issues
- Verify service status: `make status`
- Restart services: `make restart-api`
- Check firewall settings
- Validate endpoint URLs

---

*For more advanced usage patterns, see the [Examples](examples/) directory and [API Documentation](API.md).*
