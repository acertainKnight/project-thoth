# Thoth Multi-Agent Framework v3: Minimal Integration Approach

> **Core Principle:** Maximize reuse of existing Thoth services and patterns. Create agents as thin orchestration layers over existing functionality, not new implementations.

---

## 1. Executive Summary

This revised plan treats the multi-agent framework as an **orchestration layer** over existing Thoth services rather than a reimplementation. Key principles:

- **No New Core Logic**: Agents are thin wrappers that coordinate existing services
- **Minimal Code Changes**: Most changes are additive, not modifications
- **Service Reuse**: Every existing service becomes an agent capability
- **Pipeline Evolution**: Current pipeline becomes the default agent workflow

---

## 2. Architecture: Agents as Service Orchestrators

### 2.1 Agent = Service + Task Interface

```python
# src/thoth/agents/base.py - Minimal wrapper over existing services
from typing import Protocol
from thoth.services.base import BaseService

class AgentProtocol(Protocol):
    """Protocol that existing services already implement."""
    
    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process a task - maps to existing service methods."""
        ...

# NO NEW BASE CLASS NEEDED - Services already have what we need
```

### 2.2 Service-to-Agent Adapter Pattern

```python
# src/thoth/agents/adapters.py - Thin adapters for existing services
class ServiceAgentAdapter:
    """Adapt existing services to agent interface without modification."""
    
    def __init__(self, service: BaseService, method_mapping: dict[str, str]):
        self.service = service
        self.method_mapping = method_mapping
    
    async def process(self, task: dict[str, Any]) -> dict[str, Any]:
        """Route task to appropriate service method."""
        task_type = task.get("type")
        method_name = self.method_mapping.get(task_type)
        
        if not method_name:
            raise ValueError(f"Unknown task type: {task_type}")
        
        method = getattr(self.service, method_name)
        return await method(**task.get("payload", {}))

# Create agents from existing services with zero service modifications
AGENT_REGISTRY = {
    "DocumentProcessor": ServiceAgentAdapter(
        service_manager.processing,
        {
            "ocr": "ocr_to_markdown",
            "analyze": "analyze_content",
            "process_pdf": "process_document"
        }
    ),
    "CitationMiner": ServiceAgentAdapter(
        service_manager.citation,
        {
            "extract": "extract_citations",
            "format": "format_citations",
            "locate_pdf": "locate_pdf"
        }
    ),
    "Researcher": ServiceAgentAdapter(
        service_manager.rag,
        {
            "search": "search",
            "query": "query_knowledge",
            "index": "index_document"
        }
    )
}
```

---

## 3. Leveraging Existing Pipeline as Default Agent Workflow

### 3.1 Pipeline as Agent Orchestrator

```python
# src/thoth/agents/orchestrator.py - Minimal orchestrator
from thoth.pipeline import ThothPipeline
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline

class AgentOrchestrator:
    """Orchestrate agents using existing pipeline logic."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        # Reuse existing pipelines as orchestration templates
        self.document_pipeline = OptimizedDocumentPipeline(service_manager)
        self.knowledge_pipeline = KnowledgePipeline(service_manager)
        
    async def execute_workflow(self, goal: str) -> Any:
        """Execute workflow using existing pipeline methods."""
        
        # For PDF processing, use existing pipeline directly
        if "pdf" in goal.lower():
            pdf_path = self._extract_pdf_path(goal)
            return await self.document_pipeline.process_pdf_async(pdf_path)
        
        # For knowledge tasks, use knowledge pipeline
        elif "research" in goal.lower():
            query = self._extract_query(goal)
            return await self.knowledge_pipeline.process_query(query)
        
        # Dynamic agent composition for new workflows
        else:
            return await self._compose_dynamic_workflow(goal)
```

### 3.2 Minimal Pipeline Modifications

```python
# src/thoth/pipeline.py - Add agent mode with minimal changes
class ThothPipeline:
    """Existing pipeline with optional agent coordination."""
    
    def __init__(self, *args, **kwargs):
        # All existing initialization unchanged
        super().__init__(*args, **kwargs)
        
        # Single addition: agent mode flag
        self.agent_mode = kwargs.get('agent_mode', False)
    
    async def process_pdf(self, pdf_path: Path, **kwargs):
        """Existing method with optional agent coordination."""
        
        if self.agent_mode:
            # Emit events for agent monitoring
            await self._emit_agent_event("task_started", {"type": "process_pdf"})
        
        # ALL EXISTING LOGIC REMAINS UNCHANGED
        result = await self._existing_process_pdf_logic(pdf_path, **kwargs)
        
        if self.agent_mode:
            await self._emit_agent_event("task_completed", {"result": result})
        
        return result
```

---

## 4. Dynamic Agent Creation via Service Composition

### 4.1 Agent Builder Using Existing Services

```python
# src/thoth/agents/builder.py - Compose agents from existing services
class AgentBuilder:
    """Build custom agents by composing existing service capabilities."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.available_capabilities = self._map_service_capabilities()
    
    def _map_service_capabilities(self) -> dict[str, list[str]]:
        """Map existing service methods as agent capabilities."""
        return {
            "document_processing": [
                "ocr_to_markdown",  # ProcessingService
                "analyze_content",  # ProcessingService
                "extract_text"     # ProcessingService
            ],
            "citation_management": [
                "extract_citations",  # CitationService
                "format_citations",   # CitationService
                "build_graph"        # CitationService
            ],
            "research": [
                "web_search",        # WebSearchService
                "search_arxiv",      # DiscoveryService
                "query_knowledge"    # RAGService
            ],
            "knowledge_management": [
                "create_note",       # NoteService
                "update_tags",       # TagService
                "index_content"      # RAGService
            ]
        }
    
    async def create_agent_from_description(self, description: str) -> dict:
        """Create agent configuration from natural language."""
        
        # Use LLMService to parse description
        capabilities_needed = await self.service_manager.llm.extract_capabilities(
            description
        )
        
        # Map to existing service methods
        service_methods = []
        for cap in capabilities_needed:
            if methods := self._find_matching_methods(cap):
                service_methods.extend(methods)
        
        return {
            "name": self._generate_agent_name(description),
            "capabilities": service_methods,
            "service_routing": self._create_routing_table(service_methods)
        }
```

---

## 5. Existing Services as Agent Capabilities (No Modifications)

### 5.1 Service Capability Mapping

| Existing Service | Agent Capabilities | No Code Changes Needed |
|-----------------|-------------------|------------------------|
| ProcessingService | OCR, Analysis, Text Extraction | ✓ |
| CitationService | Citation Mining, Graph Building | ✓ |
| RAGService | Semantic Search, Indexing | ✓ |
| WebSearchService | Web Research, Fact Checking | ✓ |
| DiscoveryService | Paper Discovery, Monitoring | ✓ |
| NoteService | Note Generation, Formatting | ✓ |
| TagService | Tag Management, Suggestions | ✓ |
| LLMService | All LLM Operations | ✓ |

### 5.2 MCP Tools as Agent Actions

```python
# src/thoth/agents/mcp_adapter.py - Reuse existing MCP tools
from thoth.mcp.server import ThothMCPServer

class MCPAgentAdapter:
    """Use existing MCP tools as agent actions without modification."""
    
    def __init__(self, mcp_server: ThothMCPServer):
        self.mcp_server = mcp_server
        # All MCP tools automatically become agent capabilities
        self.tools = mcp_server.list_tools()
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute MCP tool as agent action."""
        # Directly use existing MCP tool implementation
        return await self.mcp_server.call_tool(tool_name, arguments)
```

---

## 6. Minimal FastAPI Router Addition

```python
# src/thoth/server/routers/agents.py - Thin router over existing functionality
@router.post("/v2/orchestrate")
async def orchestrate_task(
    goal: str,
    service_manager: ServiceManager = Depends(get_service_manager)
):
    """Orchestrate existing services to achieve goal."""
    
    # Reuse existing pipeline for standard tasks
    if "process" in goal and "pdf" in goal:
        # Extract PDF path from goal
        pdf_path = extract_pdf_path(goal)
        # Use existing pipeline
        pipeline = ThothPipeline(service_manager=service_manager)
        return await pipeline.process_pdf(pdf_path)
    
    # For complex goals, compose services dynamically
    orchestrator = AgentOrchestrator(service_manager)
    return await orchestrator.execute_workflow(goal)
```

---

## 7. Obsidian Plugin: Minimal Extensions

### 7.1 Reuse Existing UI Components

```typescript
// Extend existing ChatView instead of creating new components
export class EnhancedChatView extends ChatView {
    // Add agent selection to existing chat
    
    async onOpen() {
        await super.onOpen();  // All existing functionality
        
        // Add single dropdown for agent selection
        this.addAgentSelector();
    }
    
    private addAgentSelector() {
        // Minimal addition to existing UI
        const selector = this.containerEl.createEl('select', {
            cls: 'thoth-agent-selector'
        });
        
        // Populate with available service groupings
        ['Document Processing', 'Research', 'Knowledge Management'].forEach(
            group => {
                selector.createEl('option', { text: group, value: group });
            }
        );
    }
}
```

### 7.2 Settings: Single Toggle

```typescript
// Add to existing ThothSettings interface
export interface ThothSettings {
    // ... all existing settings ...
    
    // Single new setting
    enableAgentMode: boolean;  // Default: false for compatibility
}
```

---

## 8. Safety Through Existing Mechanisms

### 8.1 Leverage Existing Safety Features

- **File Operations**: ProcessingService already validates paths
- **API Rate Limiting**: Already implemented in services
- **Error Handling**: Existing try-catch in all services
- **Logging**: Existing loguru logging throughout

### 8.2 Minimal Safety Additions

```python
# src/thoth/agents/safety.py - Thin safety layer
class AgentSafetyWrapper:
    """Wrap existing services with additional safety checks."""
    
    def __init__(self, service: BaseService):
        self.service = service
        self.original_methods = {}
        
    def add_safety_check(self, method_name: str, check_fn: Callable):
        """Add safety check to existing method without modifying it."""
        original = getattr(self.service, method_name)
        
        async def wrapped(*args, **kwargs):
            # Safety check
            if not await check_fn(*args, **kwargs):
                raise SafetyViolation(f"Safety check failed for {method_name}")
            # Call original method
            return await original(*args, **kwargs)
        
        setattr(self.service, method_name, wrapped)
```

---

## 9. Implementation Strategy: Incremental Addition

### Phase 1: Agent Adapters (Week 1)
1. Create `ServiceAgentAdapter` class
2. Map existing services to agent interface
3. No modifications to existing services

### Phase 2: Orchestration Layer (Week 2)
1. Create minimal `AgentOrchestrator`
2. Reuse existing pipeline logic
3. Add event emission for monitoring

### Phase 3: API Extension (Week 3)
1. Add single new router endpoint
2. Reuse existing authentication/validation
3. Stream results using existing SSE setup

### Phase 4: Obsidian Integration (Week 4)
1. Extend existing ChatView
2. Add agent selector dropdown
3. Reuse all existing communication code

---

## 10. Key Advantages of This Approach

1. **Minimal Code Changes**: 90% addition, 10% modification
2. **No Breaking Changes**: All existing code paths unchanged
3. **Immediate Functionality**: Agents work with all existing features
4. **Maintainability**: No duplicate logic to maintain
5. **Performance**: No overhead when agent mode disabled
6. **Testing**: Existing tests continue to pass

---

## Conclusion

This approach treats multi-agent capabilities as a **coordination layer** over existing Thoth services rather than a reimplementation. By reusing existing services as agent capabilities, we:

- Minimize development effort
- Maintain backward compatibility
- Leverage proven, tested code
- Add powerful orchestration with minimal complexity

The result is a system that showcases advanced AI agent capabilities while demonstrating engineering excellence through maximum code reuse and minimal system disruption.