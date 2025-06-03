# Model Context Protocol (MCP) Framework for Thoth Research Assistant

## 🏗️ **Modern Architecture (LangChain Best Practices)**

The Thoth Research Assistant now follows modern LangChain best practices with automatic fallback:

### **1. Modern LangGraph Agent (Preferred)**
- **Uses**: `create_react_agent` from LangGraph prebuilt components
- **Memory**: Built-in `MemorySaver` with thread-based persistence
- **Approach**: Natural tool selection without forced prompts
- **Benefits**: Cleaner, more maintainable, follows LangChain conventions

```python
# Modern approach (automatically used when available)
agent = create_react_agent(
    llm=self.llm,
    tools=tools,
    state_modifier="You are a helpful research assistant...",
    checkpointer=MemorySaver()
)
```

### **2. Legacy Agent Executor (Fallback)**
- **Uses**: `create_openai_functions_agent` + `AgentExecutor`
- **Memory**: Manual `MessagesPlaceholder` management
- **Approach**: Enhanced prompts with tool guidance
- **Benefits**: Guaranteed compatibility, more control over behavior

### **3. Intelligent Routing**
```
User Request → Modern Agent (try first)
                     ↓ (if fails)
              → Legacy Agent (fallback)
                     ↓ (if fails)
              → Graph-based Handler (last resort)
```

## 🧠 **Conversation Memory**

The Thoth Research Assistant supports multiple levels of conversation memory:

### **Session Memory (Default)**
- Conversation history maintained by the calling application
- Memory persists only during the current session
- Caller manages history truncation (typically last 20 messages)

### **Persistent Memory (Optional)**
- Conversations saved to disk between sessions
- Automatically loaded when agent starts
- Limited to last 100 messages to prevent file bloat

```python
# Enable persistent memory
agent = ResearchAssistantAgent(
    enable_persistent_memory=True,
    memory_file="path/to/conversation_memory.json"  # optional
)

# Get conversation history
history = agent.get_conversation_history()

# Clear memory
agent.clear_conversation_memory()
```

### **Memory Integration**
- **Tool-calling mode**: Uses conversation history for context-aware responses
- **Legacy mode**: Conversation history flows through LangGraph state
- **Hybrid approach**: Combines persistent + session memory automatically

### **Memory Format**
```json
{
  "conversation_history": [
    {"role": "user", "content": "What discovery sources are available?"},
    {"role": "agent", "content": "Here are your current discovery sources..."}
  ],
  "last_updated": "2024-01-15T10:30:00"
}
```

## 📚 **LangChain Best Practices Compliance**

Our implementation follows current LangChain recommendations:

### **✅ What We Follow**
- **LangGraph over AgentExecutor**: Primary use of `create_react_agent` ([LangChain docs](https://python.langchain.com/docs/modules/agents/))
- **Built-in Memory**: `MemorySaver` for thread-based persistence ([LangChain memory docs](https://python.langchain.com/docs/how_to/chatbots_tools/))
- **Natural System Prompts**: Simple, conversational instructions rather than aggressive commands
- **MessagesPlaceholder**: Proper chat history integration in prompts
- **Tool Decorators**: Standard `Tool` class usage for function definitions

### **🔄 Intelligent Fallbacks**
Unlike typical implementations, we provide **graceful degradation**:
1. **Modern LangGraph** (when available) → Natural tool selection
2. **Legacy AgentExecutor** (compatibility) → Enhanced prompts
3. **Graph-based Handlers** (conversational) → Structured workflows

### **📖 Based on LangChain Documentation**
- [Creating Agents](https://python.langchain.com/docs/modules/agents/) - Core agent patterns
- [Chatbots with Tools](https://python.langchain.com/docs/how_to/chatbots_tools/) - Memory and conversation handling
- [Multi-Agent Workflows](https://www.intuz.com/blog/building-multi-ai-agent-workflows-with-langchain) - Modern patterns

This approach ensures **maximum compatibility** while following **current best practices**.

## Key Features

### 🎯 **Intelligent Request Routing**
- **Tool-Calling Mode**: For structured requests (create, list, run, delete operations)
- **Legacy Conversational Mode**: For greetings, explanations, and help requests
- **Automatic Fallback**: Gracefully handles failures by switching modes

### 🛠️ **Comprehensive Tool Coverage**
The framework exposes **14 tools** covering all functionality:
- **4 Query Management Tools**
- **8 Discovery Source Tools**
- **1 Article Evaluation Tool**
- **1 Help Tool**

### 🔄 **Hybrid Architecture Benefits**
- Model chooses appropriate tools automatically
- No rigid keyword matching required
- Maintains conversational UX for appropriate requests
- JSON-structured tool inputs for precision
- Easy to extend with new capabilities

## Available Tools

### Query Management Tools

| Tool | Description | Input Format |
|------|-------------|--------------|
| `list_queries` | Lists all research queries | No input needed |
| `get_query` | Gets detailed query info | `{"query_name": "name"}` |
| `create_query` | Creates new research query | Full query JSON config |
| `delete_query` | Deletes a query | `{"query_name": "name"}` |

### Discovery Source Tools

| Tool | Description | Input Format |
|------|-------------|--------------|
| `list_discovery_sources` | Lists all sources with status | No input needed |
| `get_discovery_source` | Gets detailed source config | `{"source_name": "name"}` |
| `create_discovery_source` | Creates source with full config | Complete source JSON |
| `create_arxiv_source` | Creates ArXiv source (simplified) | `{"name": "...", "keywords": [...]}` |
| `create_pubmed_source` | Creates PubMed source (simplified) | `{"name": "...", "keywords": [...]}` |
| `update_discovery_source` | Updates existing source | `{"source_name": "...", "field": "value"}` |
| `delete_discovery_source` | Deletes a source | `{"source_name": "name"}` |
| `run_discovery` | Runs discovery process | `{"source_name": "...", "max_articles": 10}` |

### Analysis & Help Tools

| Tool | Description | Input Format |
|------|-------------|--------------|
| `evaluate_article` | Evaluates article vs query | `{"query_name": "...", "article_title": "..."}` |
| `get_help` | Comprehensive help info | No input needed |

## How It Works

### 1. Request Analysis
When you send a message, the system analyzes it to determine the best approach:

```
User Input → Request Analysis → Route Decision
                                ↓
                    ┌─────────────────────────┐
                    │   Tool-Calling Mode     │  OR  │   Legacy Mode    │
                    │   (Structured Tasks)    │      │  (Conversational) │
                    └─────────────────────────┘      └─────────────────────┘
```

### 2. Tool-Calling Mode
For structured requests like:
- "Create an ArXiv source for machine learning"
- "List my discovery sources"
- "Run discovery for my_source"
- "Delete old_query"

The model automatically selects and invokes the appropriate tool with proper JSON formatting.

### 3. Legacy Conversational Mode
For conversational requests like:
- "Hello, what can you do?"
- "Help me understand this system"
- "Thank you"
- "Explain how discovery works"

The system uses the legacy graph-based handlers for a more natural conversational experience.

## Usage Examples

### Creating an ArXiv Source
```
User: "Create an ArXiv source called 'ai_papers' for artificial intelligence and machine learning"

System: [Uses create_arxiv_source tool]
→ Tool Input: {"name": "ai_papers", "keywords": ["artificial intelligence", "machine learning"], "categories": ["cs.AI", "cs.LG"]}
→ Result: "Successfully created ArXiv source 'ai_papers' with categories ['cs.AI', 'cs.LG'] and keywords ['artificial intelligence', 'machine learning']"
```

### Running Discovery
```
User: "Run discovery for ai_papers with max 5 articles"

System: [Uses run_discovery tool]
→ Tool Input: {"source_name": "ai_papers", "max_articles": 5}
→ Result: JSON with discovery results (articles found, filtered, downloaded, etc.)
```

### Conversational Request
```
User: "Hello, what can you help me with?"

System: [Uses legacy conversational mode]
→ Provides friendly greeting and comprehensive capability overview
```

## Tool Input Formats

### Simple ArXiv Source Creation
```json
{
  "name": "ml_papers",
  "keywords": ["machine learning", "neural networks", "deep learning"],
  "categories": ["cs.LG", "cs.AI"]  // Optional, defaults to cs.LG, cs.AI
}
```

### PubMed Source Creation
```json
{
  "name": "neuroscience_papers",
  "keywords": ["neuroscience", "brain imaging", "neural networks"]
}
```

### Running Discovery
```json
{
  "source_name": "ml_papers",  // Optional - runs all active if omitted
  "max_articles": 10           // Optional - uses source default if omitted
}
```

### Creating Research Query
```json
{
  "name": "transformer_research",
  "research_question": "How do transformer architectures work in NLP?",
  "keywords": ["transformer", "attention mechanism", "BERT", "GPT"],
  "required_topics": ["transformer architecture"],
  "preferred_topics": ["attention", "self-attention"],
  "excluded_topics": ["computer vision", "CNN"],
  "methodology_preferences": ["experimental", "theoretical"]
}
```

## Benefits Over Previous Implementation

### ✅ **Intelligent Tool Selection**
- **Before**: Rigid keyword matching (e.g., must say "create" + "arxiv" + quoted name)
- **After**: Natural language → Automatic tool selection

### ✅ **Comprehensive Functionality**
- **Before**: Only 3 basic tools (list_queries, list_discovery_sources, run_discovery)
- **After**: 14 tools covering all operations (create, read, update, delete)

### ✅ **Better User Experience**
- **Before**: Had to learn specific command syntax
- **After**: Natural requests work, with graceful fallback to conversation

### ✅ **Extensibility**
- **Before**: Adding functionality required modifying graph handlers
- **After**: Simply add new Tool objects to `_create_tools()`

## Architecture Details

### Hybrid Decision Logic
```python
def chat(self, user_message, ...):
    if use_tool_agent:
        # Check for conversational patterns
        if is_conversational_request(user_message):
            return legacy_mode()

        # Enhance message with tool guidance
        enhanced_message = add_tool_context(user_message)

        # Let model choose appropriate tools
        return tool_agent.invoke(enhanced_message)

    return legacy_mode()  # Fallback
```

### Tool Registration
Each tool is registered as a LangChain `Tool` object:
```python
Tool(
    name='create_arxiv_source',
    description='Create an ArXiv discovery source...',
    func=_create_arxiv_source_tool,
)
```

### Error Handling
- Tool failures automatically fall back to legacy mode
- JSON parsing errors return helpful error messages
- Missing parameters provide clear guidance

## Getting Started

1. **Start the Agent**:
   ```bash
   python -m thoth agent
   ```

2. **Try Natural Requests**:
   - "List my discovery sources"
   - "Create an ArXiv source for deep learning"
   - "Run discovery with max 5 articles"
   - "Help me understand the system"

3. **Observe Intelligent Routing**:
   - Structured requests → Tool selection
   - Conversational requests → Natural responses

## Extending the Framework

To add new functionality:

1. **Create the Tool Function**:
   ```python
   def _new_tool(input_json: str) -> str:
       # Implementation
       return result
   ```

2. **Register the Tool**:
   ```python
   tools.append(Tool(
       name='new_tool',
       description='What this tool does...',
       func=_new_tool,
   ))
   ```

3. **Update Tool Guidance** (optional):
   Add to `_enhance_message_for_tools()` method.

The framework automatically makes the new tool available to the model for intelligent selection.

## Migration Notes

### For Users
- **No breaking changes**: All existing commands still work
- **Enhanced capabilities**: Can now use natural language for any operation
- **Better discoverability**: Model suggests appropriate tools

### For Developers
- **Tool pattern**: Follow existing tool patterns for consistency
- **JSON inputs**: Use structured JSON for precise tool parameters
- **Error handling**: Return helpful error messages from tools
- **Documentation**: Update tool descriptions for better model understanding

This MCP framework provides the foundation for continuous enhancement of the Thoth Research Assistant while maintaining backward compatibility and improving user experience.
