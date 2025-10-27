# Multi-Agent Framework Implementation: PR-by-PR Plan

This document outlines a detailed, incremental implementation plan for adding the multi-agent framework to Thoth. Each PR is designed to be small, reviewable, and non-breaking.

---

## Phase 1: Foundation (No User-Visible Changes)

### PR #1: Agent Package Structure and Base Types
**Branch**: `feature/agent-package-structure`
**Size**: ~200 lines
**Risk**: None (new code only)

**Files**:
```
src/thoth/agents/
├── __init__.py
├── base.py          # Base types and protocols
├── schemas.py       # Pydantic models for Task, Result
└── exceptions.py    # Agent-specific exceptions
```

**Key Changes**:
```python
# src/thoth/agents/schemas.py
from pydantic import BaseModel
from typing import Literal, Any
from uuid import UUID

class Task(BaseModel):
    id: UUID
    type: str
    params: dict[str, Any]
    metadata: dict[str, Any] = {}
    status: Literal["pending", "running", "completed", "failed"] = "pending"

class Result(BaseModel):
    task_id: UUID
    status: Literal["success", "failure"]
    data: Any
    error: str | None = None
```

**Tests**: Unit tests for all models
**No breaking changes**: ✓

---

### PR #2: Service Agent Adapter Pattern
**Branch**: `feature/service-agent-adapter`
**Size**: ~300 lines
**Risk**: None (new code only)

**Files**:
```
src/thoth/agents/
├── adapters/
│   ├── __init__.py
│   └── service_adapter.py
└── tests/
    └── test_service_adapter.py
```

**Key Changes**:
```python
# src/thoth/agents/adapters/service_adapter.py
class ServiceAgentAdapter:
    """Wrap existing services as agents without modification."""
    
    def __init__(self, service: BaseService, capability_map: dict[str, str]):
        self.service = service
        self.capability_map = capability_map
    
    async def execute(self, task: Task) -> Result:
        method_name = self.capability_map.get(task.type)
        if not method_name:
            raise ValueError(f"Unknown task type: {task.type}")
        
        method = getattr(self.service, method_name)
        result_data = await method(**task.params)
        
        return Result(
            task_id=task.id,
            status="success",
            data=result_data
        )
```

**Tests**: Mock services, verify adapter behavior
**No breaking changes**: ✓

---

### PR #3: Agent Registry and Factory
**Branch**: `feature/agent-registry`
**Size**: ~250 lines
**Risk**: None (new code only)

**Files**:
```
src/thoth/agents/
├── registry.py      # Agent registry
├── factory.py       # Agent creation from services
└── tests/
    ├── test_registry.py
    └── test_factory.py
```

**Key Changes**:
```python
# src/thoth/agents/registry.py
class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, ServiceAgentAdapter] = {}
    
    def register(self, name: str, agent: ServiceAgentAdapter):
        self._agents[name] = agent
    
    def get(self, name: str) -> ServiceAgentAdapter:
        return self._agents.get(name)

# src/thoth/agents/factory.py
def create_default_agents(service_manager: ServiceManager) -> AgentRegistry:
    registry = AgentRegistry()
    
    # Document processing agent
    registry.register("document_processor", ServiceAgentAdapter(
        service_manager.processing,
        {
            "ocr": "ocr_to_markdown",
            "analyze": "analyze_content"
        }
    ))
    
    return registry
```

**Tests**: Registry operations, factory creation
**No breaking changes**: ✓

---

## Phase 2: Core Orchestration (Still No User Impact)

### PR #4: Event Bus for Agent Communication
**Branch**: `feature/agent-event-bus`
**Size**: ~400 lines
**Risk**: None (isolated new component)

**Files**:
```
src/thoth/agents/
├── events/
│   ├── __init__.py
│   ├── bus.py           # Event bus implementation
│   └── handlers.py      # Event handlers
└── tests/
    └── test_event_bus.py
```

**Key Changes**:
```python
# src/thoth/agents/events/bus.py
class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue = asyncio.Queue()
    
    async def publish(self, event_type: str, data: Any):
        await self._queue.put((event_type, data))
    
    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers[event_type].append(handler)
    
    async def start(self):
        while True:
            event_type, data = await self._queue.get()
            for handler in self._subscribers[event_type]:
                asyncio.create_task(handler(data))
```

**Tests**: Event publishing, subscription, async handling
**No breaking changes**: ✓

---

### PR #5: Basic Orchestrator
**Branch**: `feature/agent-orchestrator`
**Size**: ~500 lines
**Risk**: None (new component)

**Files**:
```
src/thoth/agents/
├── orchestrator.py      # Main orchestrator
├── execution.py         # Task execution logic
└── tests/
    ├── test_orchestrator.py
    └── test_execution.py
```

**Key Changes**:
```python
# src/thoth/agents/orchestrator.py
class AgentOrchestrator:
    def __init__(self, registry: AgentRegistry, event_bus: EventBus):
        self.registry = registry
        self.event_bus = event_bus
        self.running_tasks: dict[UUID, asyncio.Task] = {}
    
    async def execute_task(self, task: Task) -> Result:
        agent = self.registry.get(task.metadata.get("agent", "default"))
        if not agent:
            raise ValueError(f"No agent found for task {task.type}")
        
        await self.event_bus.publish("task_started", task)
        
        try:
            result = await agent.execute(task)
            await self.event_bus.publish("task_completed", result)
            return result
        except Exception as e:
            await self.event_bus.publish("task_failed", {"task": task, "error": str(e)})
            raise
```

**Tests**: Task execution, error handling, event emission
**No breaking changes**: ✓

---

### PR #6: ServiceManager Extension
**Branch**: `feature/service-manager-agents`
**Size**: ~150 lines
**Risk**: Low (additive changes only)

**Files**:
```
src/thoth/services/service_manager.py  # Add agent support
tests/test_service_manager.py           # Update tests
```

**Key Changes**:
```python
# src/thoth/services/service_manager.py
class ServiceManager:
    # ... existing code ...
    
    def __init__(self, config: ThothConfig | None = None):
        # ... existing initialization ...
        self._agent_registry = None
        self._agent_orchestrator = None
    
    @property
    def agent_registry(self) -> AgentRegistry | None:
        """Get agent registry if multi-agent enabled."""
        if self.config.get('multi_agent', {}).get('enabled', False):
            if not self._agent_registry:
                from thoth.agents.factory import create_default_agents
                self._agent_registry = create_default_agents(self)
            return self._agent_registry
        return None
    
    @property
    def agent_orchestrator(self) -> AgentOrchestrator | None:
        """Get agent orchestrator if multi-agent enabled."""
        if self.agent_registry:
            if not self._agent_orchestrator:
                from thoth.agents.orchestrator import AgentOrchestrator
                from thoth.agents.events.bus import EventBus
                self._agent_orchestrator = AgentOrchestrator(
                    self.agent_registry,
                    EventBus()
                )
            return self._agent_orchestrator
        return None
```

**Tests**: Verify properties return None when disabled, correct instances when enabled
**No breaking changes**: ✓ (properties return None by default)

---

## Phase 3: Pipeline Integration (Optional Features)

### PR #7: Pipeline Event Emission
**Branch**: `feature/pipeline-events`
**Size**: ~200 lines
**Risk**: Low (optional behavior)

**Files**:
```
src/thoth/pipeline.py                    # Add event emission
src/thoth/pipelines/base.py             # Add event support to base
tests/test_pipeline_events.py            # New tests
```

**Key Changes**:
```python
# src/thoth/pipeline.py
class ThothPipeline:
    def __init__(self, *args, **kwargs):
        # ... existing initialization ...
        self.emit_events = kwargs.get('emit_events', False)
        self._event_bus = None
    
    async def emit_event(self, event_type: str, data: Any):
        """Emit event if enabled and event bus available."""
        if self.emit_events and self._event_bus:
            await self._event_bus.publish(event_type, data)
    
    async def process_pdf(self, pdf_path: Path, **kwargs):
        await self.emit_event("pipeline.pdf.started", {"path": str(pdf_path)})
        
        # ALL EXISTING LOGIC UNCHANGED
        result = await self._process_pdf_internal(pdf_path, **kwargs)
        
        await self.emit_event("pipeline.pdf.completed", {"path": str(pdf_path), "result": result})
        
        return result
```

**Tests**: Verify events emitted when enabled, no events when disabled
**No breaking changes**: ✓ (events off by default)

---

### PR #8: Configuration Schema Update
**Branch**: `feature/agent-config`
**Size**: ~100 lines
**Risk**: None (additive only)

**Files**:
```
src/thoth/config/schema.py              # Add agent config schema
src/thoth/utilities/config.py           # Update config handling
tests/test_agent_config.py              # Config tests
```

**Key Changes**:
```python
# src/thoth/config/schema.py
class MultiAgentConfig(BaseModel):
    enabled: bool = False
    orchestrator_mode: Literal["in_process", "distributed"] = "in_process"
    max_concurrent_agents: int = 5
    enable_agent_creation: bool = False
    safety_level: Literal["strict", "moderate", "permissive"] = "strict"

class ThothConfig(BaseModel):
    # ... existing fields ...
    multi_agent: MultiAgentConfig = MultiAgentConfig()
```

**Tests**: Config parsing, defaults, validation
**No breaking changes**: ✓ (defaults to disabled)

---

## Phase 4: API Extensions

### PR #9: Agent Router (New Endpoints)
**Branch**: `feature/agent-api`
**Size**: ~600 lines
**Risk**: None (new endpoints only)

**Files**:
```
src/thoth/server/routers/agents.py     # New router
src/thoth/server/app.py                # Include new router
tests/test_agent_api.py                # API tests
```

**Key Changes**:
```python
# src/thoth/server/routers/agents.py
from fastapi import APIRouter, Depends, HTTPException
from src.thoth.server.dependencies import get_service_manager

router = APIRouter(prefix="/api/v2/agents", tags=["agents"])

@router.get("/")
async def list_agents(service_manager = Depends(get_service_manager)):
    """List available agents."""
    if not service_manager.agent_registry:
        raise HTTPException(status_code=404, detail="Multi-agent not enabled")
    
    return {
        "agents": list(service_manager.agent_registry._agents.keys())
    }

@router.post("/execute")
async def execute_task(
    task: Task,
    service_manager = Depends(get_service_manager)
):
    """Execute a task using agents."""
    if not service_manager.agent_orchestrator:
        raise HTTPException(status_code=404, detail="Multi-agent not enabled")
    
    result = await service_manager.agent_orchestrator.execute_task(task)
    return result

# src/thoth/server/app.py
# Add to create_app()
if config.multi_agent.enabled:
    from src.thoth.server.routers import agents
    app.include_router(agents.router)
```

**Tests**: API endpoint tests with multi-agent on/off
**No breaking changes**: ✓ (new endpoints only)

---

## Phase 5: Dynamic Agent Creation

### PR #10: Agent Builder Core
**Branch**: `feature/agent-builder`
**Size**: ~800 lines
**Risk**: None (new feature)

**Files**:
```
src/thoth/agents/builder/
├── __init__.py
├── capability_mapper.py    # Map descriptions to services
├── prompt_generator.py     # Generate agent prompts
├── agent_compiler.py       # Create agent from spec
└── tests/
```

**Key Changes**:
```python
# src/thoth/agents/builder/agent_compiler.py
class AgentCompiler:
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.capability_mapper = CapabilityMapper()
    
    async def compile_from_description(self, description: str) -> ServiceAgentAdapter:
        # Use LLM to understand requirements
        spec = await self.service_manager.llm.extract(
            description,
            schema=AgentSpecification
        )
        
        # Map to service capabilities
        capability_map = self.capability_mapper.map_to_services(
            spec.required_capabilities,
            self.service_manager
        )
        
        # Create adapter
        return ServiceAgentAdapter(
            CompositeService(self.service_manager, spec.workflow),
            capability_map
        )
```

**Tests**: Description parsing, capability mapping, agent creation
**No breaking changes**: ✓

---

### PR #11: Natural Language Agent API
**Branch**: `feature/agent-creation-api`
**Size**: ~400 lines
**Risk**: None (new endpoint)

**Files**:
```
src/thoth/server/routers/agents.py     # Add creation endpoint
tests/test_agent_creation_api.py       # API tests
```

**Key Changes**:
```python
# Add to src/thoth/server/routers/agents.py
@router.post("/create")
async def create_agent(
    request: AgentCreationRequest,
    service_manager = Depends(get_service_manager)
):
    """Create a new agent from natural language description."""
    if not service_manager.config.multi_agent.enable_agent_creation:
        raise HTTPException(status_code=403, detail="Agent creation not enabled")
    
    compiler = AgentCompiler(service_manager)
    agent = await compiler.compile_from_description(request.description)
    
    # Register the new agent
    agent_id = f"custom_{uuid4().hex[:8]}"
    service_manager.agent_registry.register(agent_id, agent)
    
    return {
        "agent_id": agent_id,
        "capabilities": list(agent.capability_map.keys())
    }
```

**Tests**: Agent creation, registration, error cases
**No breaking changes**: ✓

---

## Phase 6: Safety Framework

### PR #12: Agent Safety Layer
**Branch**: `feature/agent-safety`
**Size**: ~1000 lines
**Risk**: None (new safety features)

**Files**:
```
src/thoth/agents/safety/
├── __init__.py
├── monitor.py          # Real-time monitoring
├── validator.py        # Action validation
├── rollback.py         # Reversibility system
├── constitution.py     # AI constitution
└── tests/
```

**Key Changes**:
```python
# src/thoth/agents/safety/constitution.py
class AgentConstitution:
    PRINCIPLES = [
        Principle("data_preservation", "Never delete or corrupt user data", Priority.CRITICAL),
        Principle("truthfulness", "Always provide accurate information", Priority.CRITICAL),
        Principle("user_consent", "Require approval for destructive actions", Priority.HIGH)
    ]
    
    async def validate_action(self, action: Action) -> ValidationResult:
        for principle in self.PRINCIPLES:
            if not await principle.check(action):
                return ValidationResult(
                    allowed=False,
                    violated_principle=principle.id,
                    suggestion=await self.suggest_alternative(action)
                )
        return ValidationResult(allowed=True)
```

**Tests**: Safety validation, rollback, monitoring
**No breaking changes**: ✓

---

### PR #13: Wrap Agents with Safety
**Branch**: `feature/safe-agent-wrapper`
**Size**: ~300 lines
**Risk**: Low (wraps existing agents)

**Files**:
```
src/thoth/agents/adapters/safe_adapter.py
src/thoth/agents/factory.py               # Update to wrap with safety
tests/test_safe_adapter.py
```

**Key Changes**:
```python
# src/thoth/agents/adapters/safe_adapter.py
class SafeAgentAdapter:
    def __init__(self, agent: ServiceAgentAdapter, safety_monitor: SafetyMonitor):
        self.agent = agent
        self.safety_monitor = safety_monitor
    
    async def execute(self, task: Task) -> Result:
        # Pre-execution safety check
        validation = await self.safety_monitor.validate_task(task)
        if not validation.allowed:
            return Result(
                task_id=task.id,
                status="failure",
                error=f"Safety violation: {validation.reason}"
            )
        
        # Execute with monitoring
        with self.safety_monitor.track_execution(task):
            return await self.agent.execute(task)
```

**Tests**: Safety wrapping, validation, monitoring
**No breaking changes**: ✓

---

## Phase 7: Obsidian Plugin Integration

### PR #14: Agent Types and API Client
**Branch**: `feature/obsidian-agent-types`
**Size**: ~400 lines
**Risk**: None (TypeScript only)

**Files**:
```
obsidian-plugin/thoth-obsidian/src/
├── types/agents.ts      # Agent type definitions
├── api/agents.ts        # Agent API client
└── tests/
```

**Key Changes**:
```typescript
// src/types/agents.ts
export interface Agent {
    id: string;
    name: string;
    type: 'system' | 'custom';
    capabilities: string[];
    created_at: string;
}

export interface AgentTask {
    id: string;
    type: string;
    params: Record<string, any>;
    status: 'pending' | 'running' | 'completed' | 'failed';
}

// src/api/agents.ts
export class AgentAPIClient {
    constructor(private baseUrl: string) {}
    
    async listAgents(): Promise<Agent[]> {
        const response = await fetch(`${this.baseUrl}/api/v2/agents`);
        return response.json();
    }
    
    async executeTask(task: AgentTask): Promise<TaskResult> {
        const response = await fetch(`${this.baseUrl}/api/v2/agents/execute`, {
            method: 'POST',
            body: JSON.stringify(task)
        });
        return response.json();
    }
}
```

**Tests**: API client tests
**No breaking changes**: ✓

---

### PR #15: Agent Management UI
**Branch**: `feature/obsidian-agent-ui`
**Size**: ~800 lines
**Risk**: None (new UI components)

**Files**:
```
obsidian-plugin/thoth-obsidian/src/
├── views/
│   ├── AgentListView.ts
│   └── AgentBuilderView.ts
├── modals/
│   └── AgentManagementModal.ts
└── styles/agents.css
```

**Key Changes**:
```typescript
// src/views/AgentBuilderView.ts
export class AgentBuilderView extends ItemView {
    getViewType() { return 'thoth-agent-builder'; }
    getDisplayText() { return 'Agent Builder'; }
    
    async onOpen() {
        const container = this.containerEl.children[1];
        container.empty();
        container.addClass('thoth-agent-builder');
        
        // Chat interface for agent creation
        const chatContainer = container.createEl('div', { cls: 'agent-chat' });
        const input = container.createEl('textarea', { 
            placeholder: 'Describe the agent you want to create...' 
        });
        
        const createButton = container.createEl('button', { text: 'Create Agent' });
        createButton.onclick = async () => {
            const description = input.value;
            const agent = await this.plugin.agentAPI.createAgent({ description });
            new Notice(`Created agent: ${agent.name}`);
        };
    }
}
```

**Tests**: UI component tests
**No breaking changes**: ✓

---

### PR #16: Settings Integration
**Branch**: `feature/obsidian-agent-settings`
**Size**: ~200 lines
**Risk**: Low (settings addition)

**Files**:
```
obsidian-plugin/thoth-obsidian/src/settings.ts
obsidian-plugin/thoth-obsidian/src/main.ts
```

**Key Changes**:
```typescript
// Add to settings.ts
export interface ThothSettings {
    // ... existing settings ...
    
    // Multi-agent settings
    multiAgentEnabled: boolean;
    showAgentCommands: boolean;
    agentAPIEndpoint: string;
}

// Add to settings tab
new Setting(containerEl)
    .setName('Enable Multi-Agent Features')
    .setDesc('Enable agent creation and management (experimental)')
    .addToggle(toggle => toggle
        .setValue(this.plugin.settings.multiAgentEnabled)
        .onChange(async (value) => {
            this.plugin.settings.multiAgentEnabled = value;
            await this.plugin.saveSettings();
            // Refresh commands based on setting
            this.plugin.refreshCommands();
        }));
```

**Tests**: Settings toggle, command visibility
**No breaking changes**: ✓ (off by default)

---

## Phase 8: Advanced Features

### PR #17: Phoenix Pattern Core
**Branch**: `feature/phoenix-orchestrator`
**Size**: ~1200 lines
**Risk**: Low (optional feature)

**Files**:
```
src/thoth/agents/phoenix/
├── __init__.py
├── orchestrator.py      # Self-modifying orchestrator
├── compiler.py          # Runtime agent compilation
├── session_state.py     # State preservation
└── tests/
```

**Tests**: Hot reload, state preservation, rollback
**No breaking changes**: ✓

---

### PR #18: LangGraph Integration
**Branch**: `feature/langgraph-integration`
**Size**: ~1000 lines
**Risk**: Low (optional dependency)

**Files**:
```
src/thoth/agents/langgraph/
├── __init__.py
├── graph_builder.py     # Convert agents to LangGraph
├── workflows.py         # Pre-built workflows
└── tests/
```

**Tests**: Graph building, workflow execution
**No breaking changes**: ✓

---

### PR #19: Self-Improving Prompts
**Branch**: `feature/prompt-optimization`
**Size**: ~800 lines
**Risk**: Low (optional feature)

**Files**:
```
src/thoth/agents/optimization/
├── __init__.py
├── prompt_improver.py   # Prompt optimization
├── performance.py       # Performance tracking
└── tests/
```

**Tests**: Prompt improvement, A/B testing
**No breaking changes**: ✓

---

### PR #20: Documentation and Examples
**Branch**: `docs/multi-agent`
**Size**: ~2000 lines
**Risk**: None (documentation only)

**Files**:
```
docs/
├── multi-agent/
│   ├── getting-started.md
│   ├── creating-agents.md
│   ├── safety.md
│   └── examples/
examples/
├── agents/
│   ├── research_agent.py
│   ├── custom_agent.py
│   └── workflows.py
```

---

## Rollout Strategy

### Stage 1: Silent Rollout (PRs 1-8)
- Deploy foundation code
- No user-visible changes
- Monitor for any issues

### Stage 2: API Beta (PRs 9-13)
- Enable API endpoints for beta users
- Gather feedback on agent functionality
- Ensure safety measures work correctly

### Stage 3: UI Integration (PRs 14-16)
- Roll out Obsidian plugin features
- Behind feature flag initially
- Progressive rollout to users

### Stage 4: Advanced Features (PRs 17-19)
- Enable Phoenix pattern
- Add LangGraph workflows
- Enable prompt optimization

### Stage 5: General Availability (PR 20)
- Full documentation
- Remove beta labels
- Enable by default for new installs

---

## Success Criteria

Each PR must:
1. Pass all existing tests (no regressions)
2. Include comprehensive new tests (>90% coverage)
3. Be reviewed by at least 2 team members
4. Include documentation updates
5. Maintain backward compatibility
6. Follow existing code style

## Risk Mitigation

- **Feature flags** at every level
- **Gradual rollout** with monitoring
- **Rollback plan** for each PR
- **Performance benchmarks** to ensure no degradation
- **Security review** for agent creation features