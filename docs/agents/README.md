# Thoth Agent System

The Thoth Agent System provides Claude Code-style subagent creation and management using Letta as the orchestration framework. This system allows users to create specialized AI agents through natural language and interact with them using @agent mentions.

## Architecture Overview

The agent system consists of several key components:

- **ThothOrchestrator**: Main orchestrator that routes messages to appropriate agents
- **SubagentFactory**: Creates specialized agents from natural language descriptions
- **LettaToolRegistry**: Registers Thoth's tools with Letta for agent use
- **Memory Integration**: Advanced persistent memory using Letta's memory system

## Quick Start

### Prerequisites

1. **Letta Server**: The system requires a running Letta server
   ```bash
   # Start Letta server (usually runs on port 8283)
   docker-compose up letta
   ```

2. **Thoth API Server**: Start the Thoth server with agent support
   ```bash
   make start-api
   # or
   python -m thoth api --host 0.0.0.0 --port 8000
   ```

### Using Agents

#### Creating Agents

You can create agents through natural language descriptions:

```
"create an agent that analyzes citation patterns in research papers"
"make a discovery agent for machine learning papers"
"build an agent that helps with reference formatting"
```

#### Using Agents

Once created, interact with agents using @mentions:

```
"@citation-analyzer analyze the references in this paper"
"@discovery-agent find papers about transformer architectures"
"@reference-formatter format these citations in APA style"
```

#### Listing Agents

```
"list my agents"
"show available agents"
"what agents do I have"
```

## Agent Types

The system supports several specialized agent types:

### Research Agents
- **Purpose**: General research assistance, literature reviews
- **Tools**: Paper search, document analysis, web search
- **Example**: "create a research agent for neuroscience studies"

### Analysis Agents
- **Purpose**: Deep document analysis, critical evaluation
- **Tools**: Document analysis, citation extraction, comparison tools
- **Example**: "create an analysis agent for methodology review"

### Discovery Agents
- **Purpose**: Finding and monitoring research papers
- **Tools**: Multi-source paper discovery, search optimization
- **Example**: "create a discovery agent for AI safety papers"

### Citation Agents
- **Purpose**: Citation analysis and bibliography management
- **Tools**: Citation extraction, formatting, impact analysis
- **Example**: "create a citation agent for reference management"

### Synthesis Agents
- **Purpose**: Combining insights from multiple sources
- **Tools**: Summary generation, knowledge integration
- **Example**: "create a synthesis agent for literature reviews"

## Configuration

### Environment Variables

```bash
# Letta server configuration
LETTA_SERVER_URL=http://localhost:8283

# Agent workspace
THOTH_WORKSPACE_DIR=/path/to/workspace

# Enable agent system (default: true if Letta available)
THOTH_ENABLE_AGENTS=true
```

### Configuration File

```yaml
# config.yml
agents:
  enabled: true
  letta_url: "http://localhost:8283"
  workspace_dir: "./workspace"
  default_tools:
    research: ["search_articles", "analyze_document", "web_search"]
    analysis: ["analyze_document", "extract_citations", "compare_documents"]
    discovery: ["discover_papers", "monitor_sources", "search_optimization"]
```

## API Integration

### Agent Chat Endpoint

```http
POST /agents/chat
Content-Type: application/json

{
  "message": "create an agent that analyzes citations",
  "user_id": "researcher_123",
  "conversation_id": "optional_conversation_id"
}
```

### List Agents Endpoint

```http
GET /agents/list

Response:
{
  "agents": [
    {
      "name": "citation-analyzer",
      "description": "Analyzes citation patterns",
      "type": "system",
      "capabilities": ["Citation analysis", "Reference extraction"]
    }
  ],
  "total_count": 1,
  "system_count": 1,
  "user_count": 0
}
```

## Obsidian Integration

The Obsidian plugin includes an **Agents** tab for managing agents:

### Features
- **Agent Browser**: View all available agents with descriptions
- **Quick Creation**: Create agents through guided dialog
- **One-Click Usage**: Switch to chat and insert @agent mentions
- **Agent Status**: Monitor agent availability and health

### Usage in Obsidian
1. Open Thoth chat interface (Ctrl/Cmd + Shift + T)
2. Click the **🤖 Agents** tab
3. Use **+ Create Agent** or type creation commands in chat
4. Click **Use Agent** to quickly mention agents in chat

## Advanced Features

### Memory Persistence
Agents maintain persistent memory across sessions:
- **Core Memory**: Agent identity and key information
- **Episodic Memory**: Conversation history and interactions
- **Archival Memory**: Long-term knowledge storage

### Tool Assignment
Agents automatically receive appropriate tools based on their type:
- Research agents get paper search and analysis tools
- Citation agents get reference extraction and formatting tools
- Discovery agents get multi-source search capabilities

### Multi-Agent Coordination
- Agents can work together on complex tasks
- Orchestrator handles routing between agents
- Maintains conversation context across agent switches

## Troubleshooting

### Common Issues

**Agent creation fails**
- Ensure Letta server is running and accessible
- Check LETTA_SERVER_URL configuration
- Verify workspace directory permissions

**Agents not responding**
- Check agent status via `/agents/status` endpoint
- Verify tool registration completed successfully
- Review logs for Letta connection issues

**Memory not persisting**
- Ensure workspace directory has write permissions
- Check Letta database connectivity
- Verify memory configuration in agent setup

### Debug Mode

Enable debug logging:
```bash
export THOTH_LOG_LEVEL=DEBUG
python -m thoth api --host 0.0.0.0 --port 8000
```

### Health Checks

Check system health:
```bash
curl http://localhost:8000/agents/status
curl http://localhost:8000/agents/list
```

## Development

### Adding New Agent Types

1. **Update SubagentFactory**: Add new type to `TOOL_SETS` and `PROMPT_TEMPLATES`
2. **Register Tools**: Ensure appropriate tools are available in `LettaToolRegistry`
3. **Update Tests**: Add test cases for new agent type
4. **Documentation**: Update this README with new type information

### Custom Tool Integration

To add custom tools for agents:

1. **Implement Tool**: Create MCP-compatible tool class
2. **Register Tool**: Add to `MCP_TOOL_CLASSES` in tools module
3. **Categorize**: Update tool categorization in `LettaToolRegistry`
4. **Test**: Add integration tests

## Limitations

- **Letta Dependency**: Full functionality requires running Letta server
- **Memory Scope**: Memory persistence depends on Letta's capabilities
- **Concurrent Limits**: Agent interactions may have rate limits
- **Tool Availability**: Agent capabilities limited by registered tools

## Future Enhancements

- **Visual Agent Builder**: GUI for creating complex agents
- **Agent Templates**: Pre-built agent configurations
- **Performance Analytics**: Agent usage and effectiveness metrics
- **Multi-Model Support**: Different LLM backends per agent
- **Agent Marketplace**: Sharing and discovering community agents
