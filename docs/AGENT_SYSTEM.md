# Thoth Agent System Documentation

The Thoth Research Assistant features a sophisticated agentic system built on LangGraph with comprehensive tool integration and memory management. This document details the agent architecture, capabilities, and usage patterns.

## Architecture Overview

### Core Components

#### 1. Research Assistant Agent (`src/thoth/ingestion/agent_v2/core/agent.py`)

The main agent is implemented using LangGraph's modern graph-based architecture:

```python
class ResearchAssistant:
    """
    Modern research assistant agent using LangGraph and MCP framework.

    Features:
    - Memory-enabled conversations
    - Dynamic tool selection
    - State management
    - Token usage tracking
    """
```

#### 2. Agent State Management (`src/thoth/ingestion/agent_v2/core/state.py`)

Maintains conversation context and research state:

```python
class ResearchAgentState(TypedDict):
    """State schema for the research agent."""

    messages: List[BaseMessage]
    current_query: Optional[str]
    discovered_papers: List[Any]
    analysis_results: List[Any]
    conversation_memory: Dict[str, Any]
```

#### 3. Tool Registry (`src/thoth/ingestion/agent_v2/tools/`)

Comprehensive toolkit organized by functionality:

- **Analysis Tools**: Paper evaluation, topic analysis, related work discovery
- **Discovery Tools**: Source management, paper discovery, scheduling
- **PDF Tools**: Document processing, content extraction, metadata analysis
- **Query Tools**: Research query management and evaluation
- **RAG Tools**: Knowledge base querying and context retrieval
- **Web Tools**: Web search and content scraping

#### 4. Memory System (`src/thoth/memory/`)

Advanced persistent memory system using Letta framework for sophisticated conversation and research context management:

```python
# Agent with memory enabled
agent = create_research_assistant(
    service_manager=service_manager,
    enable_memory=True,           # Uses Letta-based persistent memory
    use_mcp_tools=True           # Model Context Protocol tools
)
await agent.async_initialize()   # Required for memory system loading
```

**Memory Features:**
- **Multi-Scope Memory**: Core memory (facts), episodic memory (conversations), archival memory (deep context)
- **Salience-Based Retention**: Intelligent scoring system for memory importance
- **Cross-Session Persistence**: Conversations continue seamlessly across sessions
- **Contextual Enrichment**: Memory entries enhanced with metadata and relationships
- **LangGraph Integration**: Full compatibility with conversation checkpointing

**Memory Architecture:**
```python
# Memory scopes automatically managed
memory_store = ThothMemoryStore()

# Core memory: Long-term facts and preferences
await memory_store.write_memory(
    user_id="researcher_1",
    content="User focuses on transformer architectures",
    scope="core"
)

# Episodic memory: Conversation interactions
await memory_store.write_memory(
    user_id="researcher_1",
    content="Discussed attention mechanisms in detail",
    scope="episodic"
)

# Memory retrieval with salience filtering
memories = await memory_store.read_memories(
    user_id="researcher_1",
    min_salience=0.7  # Only high-importance memories
)
```

## Available Tools

### Analysis Tools

#### `evaluate_article`
Evaluates how well an article matches a research query.

**Parameters:**
- `article_title` (string): Title of the article to evaluate
- `query_name` (string): Name of the query to use for evaluation

**Usage:**
```bash
python -m thoth agent chat
# In chat: "Evaluate the paper 'Attention Is All You Need' against my transformer_models query"
```

#### `analyze_research_topic`
Performs comprehensive analysis of papers on a specific research topic.

**Parameters:**
- `topic` (string): Research topic to analyze
- `max_papers` (integer): Maximum papers to include in analysis
- `analysis_type` (string): Type of analysis ("overview", "trends", "gaps")

#### `find_related_work`
Discovers papers related to a given research topic or paper.

**Parameters:**
- `reference_paper` (string): Title of reference paper
- `max_results` (integer): Maximum number of related papers to find
- `similarity_threshold` (float): Minimum similarity score

### Discovery Tools

#### `list_discovery_sources`
Lists all configured discovery sources and their status.

**Returns:** JSON list of discovery sources with metadata

#### `create_discovery_source`
Creates a new discovery source for automated paper collection.

**Parameters:**
- `name` (string): Unique name for the source
- `source_type` (string): Type ("arxiv", "semantic_scholar", "web_search")
- `query` (string): Search query for the source
- `max_articles` (integer): Maximum articles to discover
- `schedule_interval` (integer): Update interval in minutes

#### `update_discovery_source`
Updates configuration of an existing discovery source.

#### `delete_discovery_source`
Removes a discovery source.

### Query Management Tools

#### `list_queries`
Lists all research queries with their metadata.

#### `create_query`
Creates a new research query for filtering and evaluation.

**Parameters:**
- `name` (string): Unique query name
- `description` (string): Query description
- `keywords` (list): List of relevant keywords
- `inclusion_criteria` (string): Criteria for including papers
- `exclusion_criteria` (string): Criteria for excluding papers

#### `evaluate_query_performance`
Evaluates how well a query performs in finding relevant papers.

### RAG and Knowledge Tools

#### `search_knowledge_base`
Searches the RAG knowledge base for relevant information.

**Parameters:**
- `query` (string): Search query
- `max_results` (integer): Maximum results to return
- `include_metadata` (boolean): Include document metadata

#### `add_to_knowledge_base`
Adds documents to the knowledge base for RAG retrieval.

#### `get_paper_analysis`
Retrieves detailed analysis of a specific paper.

### PDF Processing Tools

#### `process_pdf_document`
Processes a PDF document with full extraction capabilities.

**Parameters:**
- `file_path` (string): Path to PDF file
- `extract_citations` (boolean): Extract bibliography
- `extract_metadata` (boolean): Extract paper metadata
- `extract_figures` (boolean): Extract figure captions
- `auto_tag` (boolean): Automatically generate tags

#### `monitor_pdf_directory`
Sets up monitoring for a directory to auto-process new PDFs.

## Agent Interaction Patterns

### 1. Interactive Chat Mode

Start an interactive session with the research assistant:

```bash
python -m thoth agent chat
```

**Example Conversation:**
```
User: Show me my discovery sources

Agent: I'll check your current discovery sources for you.

📋 **Your Discovery Sources:**

1. **ml_papers_arxiv** (ArXiv)
   - Query: "machine learning"
   - Status: Active
   - Max Articles: 50
   - Last Update: 2024-01-15 10:30:00
   - Found Papers: 847

2. **transformers_semantic** (Semantic Scholar)
   - Query: "transformer neural networks"
   - Status: Active
   - Max Articles: 30
   - Last Update: 2024-01-15 09:45:00
   - Found Papers: 234

Would you like me to create a new source, update an existing one, or analyze papers from any of these sources?

User: Create a new source for quantum computing papers from ArXiv

Agent: I'll create a new ArXiv discovery source for quantum computing papers.

✅ **Created Discovery Source: quantum_computing_arxiv**
- Type: ArXiv
- Query: "quantum computing"
- Max Articles: 50 (default)
- Schedule: Every 60 minutes
- Status: Active

The source is now running and will start discovering papers immediately. Would you like me to:
1. Adjust the search parameters?
2. Set up a more specific query?
3. Show you the first batch of discovered papers?

User: What papers do I have on attention mechanisms?

Agent: Let me search your knowledge base for papers about attention mechanisms.

📚 **Papers on Attention Mechanisms** (Found 23 papers)

**Key Papers:**
1. **"Attention Is All You Need"** (Vaswani et al., 2017)
   - Citations: 70,000+
   - Key contribution: Transformer architecture
   - Tags: transformer, self-attention, machine-translation

2. **"BERT: Pre-training of Deep Bidirectional Transformers"** (Devlin et al., 2018)
   - Citations: 65,000+
   - Key contribution: Bidirectional attention for language understanding
   - Tags: bert, bidirectional, pre-training

3. **"Show, Attend and Tell: Neural Image Captioning with Visual Attention"** (Xu et al., 2015)
   - Citations: 8,000+
   - Key contribution: Visual attention mechanisms
   - Tags: attention, computer-vision, image-captioning

**Research Trends:**
- 2015-2017: Visual attention in computer vision
- 2017-2019: Self-attention and transformers in NLP
- 2019-2024: Efficient attention mechanisms (sparse, linear)

Would you like me to:
1. Analyze connections between these papers?
2. Find recent developments in attention mechanisms?
3. Compare different attention approaches?
```

### 2. Direct Tool Execution

Execute specific tools through the API:

```bash
# Using the API to execute tools directly
curl -X POST http://localhost:8000/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_knowledge_base",
    "parameters": {
      "query": "attention mechanisms",
      "max_results": 10
    }
  }'
```

**Example Response:**
```json
{
  "tool_response": {
    "results": [
      {
        "title": "Attention Is All You Need",
        "content": "The Transformer model architecture...",
        "score": 0.95,
        "metadata": {
          "authors": ["Vaswani et al."],
          "year": 2017,
          "venue": "NIPS"
        }
      }
    ],
    "total_results": 10
  },
  "execution_time": 0.45
}
```

## Tool Integration and Orchestration

### Automatic Tool Selection

The agent automatically selects appropriate tools based on user intent:

```python
# User: "Find papers similar to 'Attention Is All You Need'"
# Agent uses: search_knowledge_base + find_related_work

# User: "Create a source for computer vision papers"
# Agent uses: create_discovery_source

# User: "How well does this paper match my research focus?"
# Agent uses: evaluate_article + get_paper_analysis
```

### Multi-Tool Workflows

Complex research tasks involve multiple tools:

```python
# Research Topic Analysis Workflow:
1. search_knowledge_base(topic)
2. find_related_work(key_papers)
3. analyze_research_topic(expanded_set)
4. evaluate_query_performance(current_queries)

# Discovery Setup Workflow:
1. list_discovery_sources()
2. create_discovery_source(new_config)
3. monitor_pdf_directory(watch_folder)
4. process_pdf_document(new_papers)
```

## Memory and Context Management

### Conversation Memory

The agent maintains context across interactions:

- **Session Persistence**: Conversations are saved and can be resumed
- **Research Context**: Remembers current research focus and preferences
- **Tool State**: Maintains awareness of created sources, queries, and analyses
- **User Preferences**: Learns from user interactions and adjusts behavior

### State Transitions

The agent manages state transitions through research workflows:

```
Initial State → Discovery Setup → Paper Collection → Analysis → Insights
     ↓              ↓               ↓              ↓         ↓
Empty KB → Sources Created → Papers Added → Processed → Knowledge Graph
```

## Advanced Features

### Custom Tool Integration

The agent system uses MCP (Model Context Protocol) tools. Custom tools should be implemented as MCP tools:

```python
# Add custom tools via MCP server extension
# Tools are automatically discovered through MCP protocol
# See src/thoth/mcp/tools/ for existing tool implementations
```

### Integration with External Systems

The agent can integrate with external research tools:

- **Citation Managers**: Zotero, Mendeley integration
- **Academic Databases**: Direct API access to Semantic Scholar, OpenCitations
- **Version Control**: Git integration for research project tracking
- **Note-Taking**: Obsidian plugin for seamless note integration

### Performance Optimization

The agent system includes several optimization features:

- **Token Usage Tracking**: Monitors and optimizes LLM token consumption
- **Caching**: Intelligent caching of analysis results and API responses
- **Batch Processing**: Efficient handling of multiple documents
- **Async Operations**: Non-blocking tool execution for better responsiveness

## Troubleshooting

### Common Issues

#### Agent Not Responding
```bash
# Check agent status
python -m thoth system status

# Restart agent services
python -m thoth agent restart
```

#### Tool Execution Failures
```bash
# Enable debug logging
export THOTH_LOG_LEVEL=DEBUG
python -m thoth agent chat

# Check tool registry
python -m thoth agent list-tools
```

#### Memory Issues
```bash
# Clear agent memory
python -m thoth agent clear-memory

# Reset conversation state
python -m thoth agent reset-state
```

### Performance Tuning

#### For Large Knowledge Bases
```bash
# Increase memory limits
export THOTH_AGENT_MEMORY_LIMIT=4GB
export THOTH_MAX_CONTEXT_TOKENS=16000

# Enable aggressive caching
export THOTH_ENABLE_TOOL_CACHE=true
```

#### For Faster Responses
```bash
# Use faster models for tool selection
export THOTH_TOOL_SELECTION_MODEL=gpt-3.5-turbo

# Reduce tool search space
export THOTH_MAX_TOOLS_PER_QUERY=5
```

---

The Thoth agent system provides a powerful, flexible foundation for research assistance with room for customization and extension based on specific research needs.
