# Thoth Multi-Agent System - Extensibility Guide

## Overview

The Thoth system is designed to be **highly extensible**. You can easily add:
- ✅ New MCP tools (research capabilities)
- ✅ New Letta agents (specialist workers)
- ✅ New shared memory blocks (coordination state)

This guide shows you exactly how to add each component.

---

## 🔧 Adding New MCP Tools

MCP tools are the **capabilities** that agents can use (search, analyze, process, etc.).

### Step 1: Create the Tool Class

Create a new file in `src/thoth/mcp/tools/` or add to an existing file:

```python
# src/thoth/mcp/tools/my_new_tools.py

from typing import Any
from ..base_tools import MCPTool, MCPToolCallResult

class MyCustomToolMCPTool(MCPTool):
    """Description of what this tool does."""

    @property
    def name(self) -> str:
        return 'my_custom_tool'

    @property
    def description(self) -> str:
        return 'Does something useful for research'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'parameter1': {
                    'type': 'string',
                    'description': 'First parameter'
                },
                'parameter2': {
                    'type': 'integer',
                    'description': 'Second parameter'
                }
            },
            'required': ['parameter1']
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """
        Execute the tool logic.

        Args:
            arguments: Tool parameters from input_schema

        Returns:
            MCPToolCallResult with success/error and content
        """
        try:
            param1 = arguments['parameter1']
            param2 = arguments.get('parameter2', 0)

            # Your tool logic here
            result = f"Processed {param1} with {param2}"

            return MCPToolCallResult(
                success=True,
                content=result
            )
        except Exception as e:
            return MCPToolCallResult(
                success=False,
                error=str(e)
            )
```

### Step 2: Register the Tool

Add your tool to `src/thoth/mcp/tools/__init__.py`:

```python
# Import your new tool
from .my_new_tools import MyCustomToolMCPTool

# Add to MCP_TOOL_CLASSES list
MCP_TOOL_CLASSES = [
    # ... existing tools ...
    MyCustomToolMCPTool,  # Add your tool here
]

# Add to __all__ export
__all__ = [
    # ... existing exports ...
    'MyCustomToolMCPTool',
]
```

### Step 3: Restart the MCP Server

```bash
# Restart Letta to pick up the new tool
docker-compose restart thoth-letta
```

### Step 4: Attach Tool to Agent

```python
import requests

API_BASE = "http://localhost:8283/v1"

# Get the tool ID
tools = requests.get(f"{API_BASE}/tools").json()
my_tool = next(t for t in tools if t['name'] == 'my_custom_tool')
tool_id = my_tool['id']

# Get agent's current tools
agent_id = "agent-xyz..."
agent = requests.get(f"{API_BASE}/agents/{agent_id}").json()
current_tool_ids = [t['id'] for t in agent['tools']]

# Add new tool
new_tool_ids = current_tool_ids + [tool_id]
requests.patch(
    f"{API_BASE}/agents/{agent_id}",
    json={"tool_ids": new_tool_ids}
)
```

### Real Example: Adding a "Summarize Paper" Tool

```python
# src/thoth/mcp/tools/summarization_tools.py

class SummarizePaperMCPTool(MCPTool):
    """Generate concise summary of a research paper."""

    @property
    def name(self) -> str:
        return 'summarize_paper'

    @property
    def description(self) -> str:
        return 'Generate a concise summary of a research paper including main findings, methodology, and conclusions'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_id': {
                    'type': 'string',
                    'description': 'ID of the article to summarize'
                },
                'max_length': {
                    'type': 'integer',
                    'description': 'Maximum summary length in words',
                    'default': 250
                }
            },
            'required': ['article_id']
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        article_id = arguments['article_id']
        max_length = arguments.get('max_length', 250)

        # Get article from database
        article_service = self.service_manager.article_service
        article = await article_service.get_article(article_id)

        if not article:
            return MCPToolCallResult(
                success=False,
                error=f"Article {article_id} not found"
            )

        # Generate summary (using your logic)
        summary = await self._generate_summary(article, max_length)

        return MCPToolCallResult(
            success=True,
            content=summary
        )
```

---

## 🤖 Adding New Agents

Agents are **specialists** that use tools to perform specific roles.

### Step 1: Define Agent Configuration

```python
# Create a configuration for your new agent

agent_config = {
    "name": "system_fact_checker",
    "description": "Specialist agent for verifying research claims",
    "model": "letta/letta-free",
    "embedding": "letta/letta-free",
    "system_prompt": """You are a fact-checking specialist for research claims.

Your role:
- Verify claims against source papers
- Check citation accuracy
- Flag potential contradictions
- Report findings to orchestrator

Coordinate via:
- send_message_to_agent_async to report findings
- Update research_findings memory block with verification results
"""
}
```

### Step 2: Determine Tool Allocation

Based on the agent's role, decide which tools it needs:

```python
# Example: Fact checker needs these tools
needed_tools = [
    'send_message_to_agent_async',      # Communication
    'memory_insert',                     # Memory management
    'memory_replace',
    'core_memory_append',
    'core_memory_replace',
    'get_article_details',              # Read papers
    'search_articles',                   # Find claims
    'extract_citations',                 # Verify citations
    'find_related_papers',              # Cross-reference
    'evaluate_article',                  # Quality check
]
```

### Step 3: Create Agent Script

```python
# scripts/create_fact_checker_agent.py

import requests

API_BASE = "http://localhost:8283/v1"

# Get tool IDs for needed tools
all_tools = requests.get(f"{API_BASE}/tools").json()
tool_id_map = {t['name']: t['id'] for t in all_tools}

needed_tool_names = [
    'send_message_to_agent_async',
    'memory_insert',
    'memory_replace',
    'core_memory_append',
    'core_memory_replace',
    'get_article_details',
    'search_articles',
    'extract_citations',
    'find_related_papers',
    'evaluate_article',
]

tool_ids = [tool_id_map[name] for name in needed_tool_names]

# Get shared memory block IDs (same as other agents)
existing_agent_id = "agent-10418b8d-37a5-4923-8f70-69ccc58d66ff"
existing_agent = requests.get(f"{API_BASE}/agents/{existing_agent_id}").json()
memory_blocks = existing_agent['memory']['blocks']
block_ids = [block['id'] for block in memory_blocks]

# Create the agent
response = requests.post(
    f"{API_BASE}/agents",
    json={
        "name": "system_fact_checker",
        "description": "Fact-checking specialist for research claims",
        "model": "letta/letta-free",
        "embedding": "letta/letta-free",
        "tool_ids": tool_ids,
        "block_ids": block_ids,
        "system": """You are a fact-checking specialist for research claims.

Your role:
- Verify claims against source papers
- Check citation accuracy
- Flag potential contradictions
- Report findings to orchestrator

Coordinate via:
- send_message_to_agent_async to report findings
- Update research_findings memory block with verification results
"""
    }
)

new_agent = response.json()
print(f"Created agent: {new_agent['id']}")
print(f"Name: {new_agent['name']}")
print(f"Tools: {len(new_agent['tools'])}")
print(f"Memory blocks: {len(new_agent['memory']['blocks'])}")
```

### Step 4: Run the Script

```bash
python3 scripts/create_fact_checker_agent.py
```

### Step 5: Update Architecture Documentation

Add your agent to `docs/MULTI_AGENT_ARCHITECTURE.md`:

```markdown
### 5. SYSTEM_FACT_CHECKER (Verification Specialist)

**Role**: Fact-checking specialist - Verifies research claims

**Responsibilities**:
- Verify claims against source papers
- Check citation accuracy
- Flag contradictions
- Report to orchestrator

**Tools** (10 total):
- Communication (1): send_message_to_agent_async
- Memory Management (4): memory_*, core_memory_*
- Article Access (2): get_article_details, search_articles
- Verification (3): extract_citations, find_related_papers, evaluate_article

**Does NOT Have**:
- Discovery tools (scout's job)
- Synthesis tools (expert's job)
```

---

## 🧠 Adding New Memory Blocks

Memory blocks are **shared state** that all agents can read and write.

### Step 1: Define Block Purpose

Clearly define what the block will store and why:

```python
# Example: Track research hypotheses
block_purpose = {
    "name": "research_hypotheses",
    "description": "Tracks hypotheses being tested and evidence for/against",
    "updated_by": ["orchestrator", "analysis_expert", "fact_checker"],
    "read_by": ["all_agents"],
    "structure": """
Hypothesis 1: [Statement]
Evidence For: [List]
Evidence Against: [List]
Status: [testing/supported/refuted]

Hypothesis 2: ...
"""
}
```

### Step 2: Create the Memory Block

```python
# scripts/create_research_hypotheses_block.py

import requests

API_BASE = "http://localhost:8283/v1"

# Create the block
response = requests.post(
    f"{API_BASE}/blocks",
    json={
        "label": "research_hypotheses",
        "value": """Hypothesis 1: [Not yet defined]
Evidence For: []
Evidence Against: []
Status: pending

Hypothesis 2: [Not yet defined]
Evidence For: []
Evidence Against: []
Status: pending
""",
        "limit": 5000  # Max characters
    }
)

block = response.json()
block_id = block['id']
print(f"Created memory block: {block_id}")
```

### Step 3: Attach to All Agents

```python
# Attach to all agents
agent_ids = [
    "agent-10418b8d-37a5-4923-8f70-69ccc58d66ff",  # orchestrator
    "agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5",  # analyzer
    "agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64",  # scout
    "agent-8a4183a6-fffc-4082-b40b-aab29727a3ab",  # expert
    "agent-xyz...",  # fact_checker (your new agent)
]

for agent_id in agent_ids:
    # Get current blocks
    agent = requests.get(f"{API_BASE}/agents/{agent_id}").json()
    current_block_ids = [b['id'] for b in agent['memory']['blocks']]

    # Add new block
    new_block_ids = current_block_ids + [block_id]

    # Update agent
    requests.patch(
        f"{API_BASE}/agents/{agent_id}",
        json={"block_ids": new_block_ids}
    )

    print(f"Attached block to {agent['name']}")
```

### Step 4: Document the Block

Add to `docs/SYSTEM_ARCHITECTURE_EXPLAINED.md`:

```markdown
### 7. `research_hypotheses` (block-xyz...)

**Purpose**: Tracks hypotheses being tested and supporting/contradicting evidence

**Why It Exists**:
- Research often involves testing hypotheses
- Agents need to track evidence as they read papers
- Prevents re-evaluating the same evidence multiple times
- Builds toward conclusions about hypothesis validity

**Updated By**:
- Orchestrator (defines initial hypotheses)
- Analysis Expert (evaluates evidence)
- Fact Checker (verifies claims)

**Read By**: All agents (to understand research direction)

**Structure**:
```
Hypothesis 1: Topological qubits have lower error rates
Evidence For: [paper1 shows 10x reduction, paper2 confirms]
Evidence Against: [paper3 shows similar rates in some conditions]
Status: supported
```
```

---

## 📋 Quick Reference Cheat Sheet

### Adding a Tool
1. Create tool class in `src/thoth/mcp/tools/`
2. Add to `MCP_TOOL_CLASSES` in `__init__.py`
3. Restart Letta: `docker-compose restart thoth-letta`
4. Attach to agents via API

### Adding an Agent
1. Define role and tool needs
2. Get tool IDs and memory block IDs from existing agents
3. Create via `POST /v1/agents` with tool_ids and block_ids
4. Document in architecture docs

### Adding a Memory Block
1. Define purpose and structure
2. Create via `POST /v1/blocks`
3. Attach to agents via `PATCH /v1/agents/{id}` with block_ids
4. Document in architecture docs

---

## 🎯 Best Practices

### For Tools:
- ✅ **Single Responsibility**: Each tool does ONE thing well
- ✅ **Clear Descriptions**: Agents need to understand when to use it
- ✅ **Validate Inputs**: Check parameters before processing
- ✅ **Return Structured Data**: Use consistent result formats

### For Agents:
- ✅ **Specialized Roles**: Each agent has a clear, specific job
- ✅ **Minimal Tools**: Only give tools needed for their role
- ✅ **Clear System Prompts**: Explain role, tools, and coordination
- ✅ **Attach Shared Memory**: All agents need the 6 core blocks

### For Memory Blocks:
- ✅ **Clear Structure**: Define format agents should follow
- ✅ **Bounded Size**: Set reasonable `limit` to prevent overflow
- ✅ **Document Ownership**: Who reads vs writes the block
- ✅ **Descriptive Labels**: Use clear names like `research_findings`

---

## 🚀 Example: Adding a Literature Review Agent

Let's add a complete new agent that generates literature reviews:

### 1. Create the Agent

```python
# scripts/create_literature_review_agent.py

import requests

API_BASE = "http://localhost:8283/v1"

# Get tool IDs
all_tools = requests.get(f"{API_BASE}/tools").json()
tool_map = {t['name']: t['id'] for t in all_tools}

# Literature review agent needs:
tools = [
    'send_message_to_agent_async',      # Report to orchestrator
    'memory_insert', 'memory_replace',  # Update memory
    'core_memory_append', 'core_memory_replace',
    'search_articles',                   # Find papers
    'get_article_details',              # Read papers
    'find_related_papers',              # Discover connections
    'generate_research_summary',        # Create summaries
    'analyze_topic',                    # Topic analysis
    'list_articles',                    # Browse collection
]

tool_ids = [tool_map[name] for name in tools]

# Get existing memory blocks
existing_agent = requests.get(f"{API_BASE}/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff").json()
block_ids = [b['id'] for b in existing_agent['memory']['blocks']]

# Create agent
response = requests.post(
    f"{API_BASE}/agents",
    json={
        "name": "system_literature_reviewer",
        "model": "letta/letta-free",
        "embedding": "letta/letta-free",
        "tool_ids": tool_ids,
        "block_ids": block_ids,
        "system": """You are a literature review specialist.

Your role:
- Synthesize findings across multiple papers
- Identify research gaps and trends
- Create structured literature reviews
- Report comprehensive reviews to orchestrator

You have access to:
- search_articles, get_article_details (read papers)
- find_related_papers (discover connections)
- analyze_topic (identify themes)
- generate_research_summary (create output)

Coordinate via:
- send_message_to_agent_async to report reviews
- Update research_findings with synthesis
"""
    }
)

agent = response.json()
print(f"✅ Created: {agent['name']} ({agent['id']})")
print(f"   Tools: {len(agent['tools'])}")
print(f"   Blocks: {len(agent['memory']['blocks'])}")
```

### 2. Run It

```bash
python3 scripts/create_literature_review_agent.py
```

### 3. Test It

```python
# scripts/test_literature_reviewer.py

import requests

API_BASE = "http://localhost:8283/v1"

# Get agent ID
agents = requests.get(f"{API_BASE}/agents").json()
reviewer = next(a for a in agents if a['name'] == 'system_literature_reviewer')

# Send a message to test
response = requests.post(
    f"{API_BASE}/agents/{reviewer['id']}/messages",
    json={
        "message": "Create a literature review on quantum error correction, focusing on topological approaches",
        "role": "user"
    }
)

print(response.json())
```

---

## 🔍 Debugging Tips

### Check Tool Availability
```bash
curl http://localhost:8283/v1/tools | jq '.[] | {name, id}'
```

### Check Agent Configuration
```bash
curl http://localhost:8283/v1/agents/agent-xyz... | jq '{name, tools: .tools | length, blocks: .memory.blocks | length}'
```

### Check Memory Blocks
```bash
curl http://localhost:8283/v1/agents/agent-xyz... | jq '.memory.blocks[] | {label, value}'
```

### Verify Tool Attachment
```bash
curl http://localhost:8283/v1/agents/agent-xyz... | jq '.tools[] | .name'
```

---

## 📖 Summary

The Thoth multi-agent system is designed for extensibility:

✅ **Tools** = Capabilities (what agents can DO)
✅ **Agents** = Specialists (WHO does the work)
✅ **Memory Blocks** = Shared state (HOW they coordinate)

With these three components, you can build arbitrarily complex research workflows while maintaining clean separation of concerns and efficient resource usage.

**Key Insight**: Start simple, add complexity only when needed. The current 4-agent system with 6 memory blocks handles most research tasks. Only add new components when you identify a clear gap in capabilities.
