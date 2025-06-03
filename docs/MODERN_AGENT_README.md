# Thoth Modern Research Assistant Agent

## Overview

The modern research assistant agent is a complete redesign of the original agent using LangGraph and the Model Context Protocol (MCP) framework. This new architecture provides a clean, modular, and extensible system for managing research activities.

## Architecture

```
agent_v2/
├── __init__.py              # Package exports
├── core/                    # Core agent logic
│   ├── agent.py            # Main ResearchAssistant class
│   ├── state.py            # LangGraph state management
│   └── memory.py           # Conversation memory (future)
├── tools/                   # Modular tool implementations
│   ├── base_tool.py        # Base classes and registry
│   ├── query_tools.py      # Research query management
│   ├── discovery_tools.py  # Discovery source management
│   ├── rag_tools.py        # Knowledge base tools
│   └── analysis_tools.py   # Paper analysis tools
├── chains/                  # Complex workflows (future)
└── config/                  # Configuration (future)
```

## Key Features

### 1. **Modular Tool Architecture**
- Each capability is implemented as a separate tool class
- Tools inherit from `BaseThothTool` for consistent interface
- Easy to add new tools without modifying core agent logic

### 2. **LangGraph Integration**
- Built on LangGraph for robust agent workflows
- Automatic tool routing and execution
- Built-in conversation memory management
- Proper error handling and recovery

### 3. **Type-Safe Interfaces**
- Pydantic models for all tool inputs/outputs
- Strong typing throughout the codebase
- Automatic validation of tool parameters

### 4. **MCP Framework Compliance**
- Follows Model Context Protocol best practices
- Clean separation between agent logic and tool execution
- Standardized tool descriptions and schemas

## Available Tools

### Query Management
- `list_queries` - List all research queries
- `create_query` - Create a new research query
- `get_query` - Get details of a specific query
- `edit_query` - Modify an existing query
- `delete_query` - Remove a query

### Discovery Management
- `list_discovery_sources` - Show all discovery sources
- `create_arxiv_source` - Create an ArXiv source
- `create_pubmed_source` - Create a PubMed source
- `run_discovery` - Execute discovery for sources
- `delete_discovery_source` - Remove a source

### Knowledge Base (RAG)
- `search_knowledge` - Search papers and notes
- `ask_knowledge` - Ask questions about research
- `index_knowledge` - Index documents for search
- `explain_connections` - Find paper relationships
- `rag_stats` - Show RAG system statistics

### Analysis Tools
- `evaluate_article` - Evaluate article relevance
- `analyze_topic` - Analyze research topics
- `find_related` - Find related papers

## Usage

### Basic Usage

```python
from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.pipeline import ThothPipeline

# Initialize pipeline
pipeline = ThothPipeline()

# Create agent
agent = create_research_assistant(
    llm=pipeline.llm_processor.llm,
    pipeline=pipeline,
    enable_memory=True,
)

# Chat with agent
response = agent.chat(
    message="Create an ArXiv source for machine learning papers",
    session_id="my_session",
)

print(response["response"])
```

### Advanced Usage

```python
# Custom system prompt
agent = create_research_assistant(
    llm=pipeline.llm_processor.llm,
    pipeline=pipeline,
    system_prompt="You are a specialized ML research assistant...",
)

# Get available tools
tools = agent.get_available_tools()
for tool in tools:
    print(f"{tool['name']}: {tool['description']}")

# Reset memory for a session
agent.reset_memory(session_id="my_session")
```

## Extending the Agent

### Adding a New Tool

1. Create a new tool class in the appropriate module:

```python
from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool
from pydantic import BaseModel, Field
from typing import Type

class MyToolInput(BaseModel):
    """Input schema for my tool."""
    parameter: str = Field(description="Tool parameter")

class MyNewTool(BaseThothTool):
    """Description of what this tool does."""

    name: str = "my_tool_name"
    description: str = "Clear description for the LLM"
    args_schema: Type[BaseModel] = MyToolInput

    def _run(self, parameter: str) -> str:
        """Execute the tool logic."""
        try:
            # Tool implementation
            result = do_something(parameter)
            return f"Success: {result}"
        except Exception as e:
            return self.handle_error(e)
```

2. Register the tool in the agent:

```python
# In agent.py _register_tools method
self.tool_registry.register("my_tool_name", MyNewTool)
```

### Creating Custom Workflows

Future versions will support custom chains for complex workflows:

```python
# Future capability
from thoth.ingestion.agent_v2.chains import ResearchChain

chain = ResearchChain()
chain.add_step("search_knowledge", {"query": "transformers"})
chain.add_step("analyze_topic", {"topic": "transformers"})
result = chain.run()
```

## Benefits Over Legacy Agent

| Aspect | Legacy Agent | Modern Agent |
|--------|--------------|--------------|
| **Code Organization** | Single 2864-line file | Modular structure (~1500 lines total) |
| **Extensibility** | Modify main class | Add new tool classes |
| **Testing** | Difficult to isolate | Easy unit testing per tool |
| **Memory** | Custom implementation | LangGraph built-in |
| **Tool Management** | Embedded methods | Registry pattern |
| **Type Safety** | Mixed | Full Pydantic validation |
| **Error Handling** | Scattered | Centralized in base class |

## Migration Guide

### For Users

The new agent maintains backward compatibility for core functionality:

1. **Command Line**: Use `thoth agent` as before
2. **Conversations**: Natural language works the same
3. **Features**: All capabilities are preserved

### For Developers

To migrate custom code:

1. **Tool Creation**: Convert methods to tool classes
2. **State Management**: Use `ResearchAgentState`
3. **Memory**: Leverage LangGraph's memory
4. **Testing**: Write tests for individual tools

## Configuration

The agent uses the same configuration as the main Thoth system:

```yaml
# In your Thoth config
research_agent_llm_config:
  model: "anthropic/claude-3-opus"
  max_output_tokens: 4096
  temperature: 0.7
```

## Future Enhancements

- [ ] Async tool execution
- [ ] Custom chain workflows
- [ ] Tool result caching
- [ ] Multi-agent collaboration
- [ ] Web UI integration
- [ ] Plugin system for external tools

## Troubleshooting

### Common Issues

1. **Tool Not Found**: Ensure tool is registered in `_register_tools`
2. **Memory Issues**: Check session_id is consistent
3. **Type Errors**: Verify Pydantic schemas match

### Debug Mode

```python
import logging
logging.getLogger("thoth.ingestion.agent_v2").setLevel(logging.DEBUG)
```

## Contributing

To contribute new tools:

1. Follow the tool template above
2. Add comprehensive docstrings
3. Include type hints
4. Write unit tests
5. Update this documentation

## License

Same as Thoth project - see main LICENSE file.
