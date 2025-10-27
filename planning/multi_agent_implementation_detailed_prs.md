# Multi-Agent Framework Implementation: Detailed PR-by-PR Engineering Guide

This document provides comprehensive implementation guidance for adding the multi-agent framework to Thoth. Each PR includes detailed explanations, code examples, and implementation notes.

---

## Phase 1: Foundation (No User-Visible Changes)

### PR #1: Agent Package Structure and Base Types
**Branch**: `feature/agent-package-structure`
**Size**: ~200 lines
**Duration**: 1-2 days
**Dependencies**: None

#### Purpose
Establish the foundational data structures and types that all agent functionality will build upon. This PR creates the "vocabulary" that the rest of the system will use to communicate about agents and tasks.

#### What This Implements
- **Task**: A unit of work that an agent can perform (e.g., "extract citations from this paper")
- **Result**: The outcome of executing a task
- **Base types**: Common interfaces and exceptions for the agent system

#### Detailed Implementation

**File: `src/thoth/agents/__init__.py`**
```python
"""
Thoth Agent System - Orchestration layer for intelligent service composition.

Agents are NOT replacements for services. They are orchestrators that
intelligently combine existing services to achieve complex goals.
"""

from thoth.agents.schemas import Task, Result, AgentError

__all__ = ["Task", "Result", "AgentError"]
```

**File: `src/thoth/agents/schemas.py`**
```python
"""
Core data models for the agent system.

These models define how agents communicate about work to be done.
"""

from pydantic import BaseModel, Field
from typing import Literal, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime

class Task(BaseModel):
    """
    Represents a unit of work for an agent to perform.
    
    Example:
        task = Task(
            type="extract_citations",
            params={"pdf_path": "/path/to/paper.pdf"},
            metadata={"requested_by": "user", "priority": "high"}
        )
    """
    id: UUID = Field(default_factory=uuid4)
    type: str = Field(description="The type of task (e.g., 'ocr', 'analyze')")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the task")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }

class Result(BaseModel):
    """
    The outcome of executing a task.
    
    Example:
        result = Result(
            task_id=task.id,
            status="success",
            data={"citations": [...], "count": 15}
        )
    """
    task_id: UUID
    status: Literal["success", "failure"]
    data: Any = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    completed_at: datetime = Field(default_factory=datetime.utcnow)
```

**File: `src/thoth/agents/exceptions.py`**
```python
"""Agent-specific exceptions."""

class AgentError(Exception):
    """Base exception for agent-related errors."""
    pass

class TaskExecutionError(AgentError):
    """Raised when a task fails to execute."""
    pass

class AgentNotFoundError(AgentError):
    """Raised when a requested agent doesn't exist."""
    pass

class SafetyViolationError(AgentError):
    """Raised when an action violates safety constraints."""
    pass
```

#### Testing Requirements
```python
# tests/agents/test_schemas.py
def test_task_creation():
    """Test that tasks are created with proper defaults."""
    task = Task(type="test", params={"foo": "bar"})
    assert task.id is not None
    assert task.status == "pending"
    assert task.params == {"foo": "bar"}

def test_result_serialization():
    """Test that results can be serialized to JSON."""
    result = Result(task_id=uuid4(), status="success", data={"test": True})
    json_str = result.json()
    assert "task_id" in json_str
```

#### Why This Matters
Without clear data structures, different parts of the system can't communicate effectively. These types ensure that when the orchestrator gives work to an agent, both sides understand exactly what's being requested and what the response should look like.

---

### PR #2: Service Agent Adapter Pattern
**Branch**: `feature/service-agent-adapter`
**Size**: ~300 lines
**Duration**: 2-3 days
**Dependencies**: PR #1

#### Purpose
Create the bridge between existing services (which know nothing about agents) and the agent system. This adapter pattern allows us to treat any service as an agent WITHOUT modifying the service code.

#### What This Implements
The adapter pattern wraps existing services to make them "speak agent". It's like creating a translator that converts agent tasks into service method calls.

#### Detailed Implementation

**File: `src/thoth/agents/adapters/service_adapter.py`**
```python
"""
Service Agent Adapter - Makes existing services work as agents.

This is the KEY INSIGHT of our architecture: we don't need to rewrite
services as agents. We just need to adapt their interfaces.
"""

from typing import Dict, Any, Callable
from thoth.agents.schemas import Task, Result
from thoth.services.base import BaseService
import asyncio
import time

class ServiceAgentAdapter:
    """
    Wraps an existing service to work as an agent.
    
    This adapter:
    1. Receives tasks in agent format
    2. Translates them to service method calls
    3. Wraps service responses as agent results
    
    Example:
        # Make ProcessingService work as an agent
        processing_agent = ServiceAgentAdapter(
            service=processing_service,
            capability_map={
                "ocr": "ocr_to_markdown",        # task type -> service method
                "analyze": "analyze_content",
                "extract": "extract_text"
            }
        )
        
        # Now it can handle agent tasks
        task = Task(type="ocr", params={"pdf_path": "/path/to/doc.pdf"})
        result = await processing_agent.execute(task)
    """
    
    def __init__(
        self, 
        service: BaseService, 
        capability_map: Dict[str, str],
        name: str = None
    ):
        """
        Initialize the adapter.
        
        Args:
            service: The existing service to wrap
            capability_map: Maps task types to service method names
            name: Optional name for this agent
        """
        self.service = service
        self.capability_map = capability_map
        self.name = name or f"{service.__class__.__name__}Agent"
        
        # Validate that all mapped methods exist
        for task_type, method_name in capability_map.items():
            if not hasattr(service, method_name):
                raise ValueError(
                    f"Service {service.__class__.__name__} has no method '{method_name}'"
                )
    
    async def execute(self, task: Task) -> Result:
        """
        Execute a task by calling the appropriate service method.
        
        This method:
        1. Looks up which service method to call
        2. Calls it with the task parameters
        3. Wraps the response as a Result
        """
        start_time = time.time()
        
        try:
            # Find the service method for this task type
            method_name = self.capability_map.get(task.type)
            if not method_name:
                raise ValueError(
                    f"Agent {self.name} doesn't support task type '{task.type}'. "
                    f"Supported types: {list(self.capability_map.keys())}"
                )
            
            # Get the actual method
            method = getattr(self.service, method_name)
            
            # Call it with the task parameters
            # Handle both sync and async methods
            if asyncio.iscoroutinefunction(method):
                result_data = await method(**task.params)
            else:
                result_data = method(**task.params)
            
            # Wrap as Result
            return Result(
                task_id=task.id,
                status="success",
                data=result_data,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            # Wrap failures as Result too
            return Result(
                task_id=task.id,
                status="failure",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def get_capabilities(self) -> list[str]:
        """Return the task types this agent can handle."""
        return list(self.capability_map.keys())
    
    def __repr__(self) -> str:
        return f"{self.name}(capabilities={self.get_capabilities()})"
```

**File: `src/thoth/agents/adapters/__init__.py`**
```python
from thoth.agents.adapters.service_adapter import ServiceAgentAdapter

__all__ = ["ServiceAgentAdapter"]
```

#### Testing Requirements
```python
# tests/agents/test_service_adapter.py
import pytest
from unittest.mock import Mock, AsyncMock

async def test_adapter_executes_service_method():
    """Test that adapter correctly calls service methods."""
    # Mock a service
    mock_service = Mock()
    mock_service.process_document = Mock(return_value={"text": "extracted"})
    
    # Create adapter
    adapter = ServiceAgentAdapter(
        service=mock_service,
        capability_map={"extract": "process_document"}
    )
    
    # Execute task
    task = Task(type="extract", params={"path": "/test.pdf"})
    result = await adapter.execute(task)
    
    # Verify
    assert result.status == "success"
    assert result.data == {"text": "extracted"}
    mock_service.process_document.assert_called_once_with(path="/test.pdf")

async def test_adapter_handles_unknown_task_type():
    """Test that adapter properly handles unknown task types."""
    mock_service = Mock()
    adapter = ServiceAgentAdapter(
        service=mock_service,
        capability_map={"known": "method"}
    )
    
    task = Task(type="unknown", params={})
    result = await adapter.execute(task)
    
    assert result.status == "failure"
    assert "doesn't support task type 'unknown'" in result.error
```

#### Why This Matters
This adapter is the cornerstone of our approach. Instead of rewriting ProcessingService, CitationService, etc. as agents, we wrap them. This means:
- Zero changes to existing services
- All service functionality immediately available to agents
- Services can be updated independently of the agent system

---

### PR #3: Agent Registry and Factory
**Branch**: `feature/agent-registry`
**Size**: ~250 lines
**Duration**: 1-2 days
**Dependencies**: PR #2

#### Purpose
Create a central registry where agents are stored and a factory that creates the default agents from existing services. This gives us a single place to look up available agents.

#### What This Implements
- **Registry**: A catalog of available agents
- **Factory**: Creates standard agents from Thoth's services
- **Agent discovery**: Ability to list and find agents

#### Detailed Implementation

**File: `src/thoth/agents/registry.py`**
```python
"""
Agent Registry - Central catalog of available agents.

The registry is where we keep track of all agents in the system.
Think of it as a phone book for agents.
"""

from typing import Dict, Optional, List
from thoth.agents.adapters import ServiceAgentAdapter
from thoth.agents.exceptions import AgentNotFoundError
import threading

class AgentRegistry:
    """
    Thread-safe registry for managing agents.
    
    Example:
        registry = AgentRegistry()
        registry.register("processor", processing_agent)
        registry.register("researcher", research_agent)
        
        # Later, find and use an agent
        agent = registry.get("processor")
        result = await agent.execute(task)
    """
    
    def __init__(self):
        self._agents: Dict[str, ServiceAgentAdapter] = {}
        self._lock = threading.RLock()
    
    def register(self, name: str, agent: ServiceAgentAdapter) -> None:
        """
        Register an agent with a given name.
        
        Args:
            name: Unique identifier for the agent
            agent: The agent instance to register
            
        Raises:
            ValueError: If an agent with this name already exists
        """
        with self._lock:
            if name in self._agents:
                raise ValueError(f"Agent '{name}' is already registered")
            self._agents[name] = agent
    
    def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        with self._lock:
            if name in self._agents:
                del self._agents[name]
    
    def get(self, name: str) -> ServiceAgentAdapter:
        """
        Get an agent by name.
        
        Args:
            name: The agent's registered name
            
        Returns:
            The requested agent
            
        Raises:
            AgentNotFoundError: If no agent with this name exists
        """
        with self._lock:
            agent = self._agents.get(name)
            if not agent:
                available = list(self._agents.keys())
                raise AgentNotFoundError(
                    f"No agent named '{name}'. Available agents: {available}"
                )
            return agent
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all registered agents with their capabilities.
        
        Returns:
            List of agent information dictionaries
        """
        with self._lock:
            return [
                {
                    "name": name,
                    "type": agent.__class__.__name__,
                    "capabilities": agent.get_capabilities()
                }
                for name, agent in self._agents.items()
            ]
    
    def find_by_capability(self, capability: str) -> List[str]:
        """
        Find all agents that have a specific capability.
        
        Args:
            capability: The task type to search for
            
        Returns:
            List of agent names that can handle this task type
        """
        with self._lock:
            return [
                name for name, agent in self._agents.items()
                if capability in agent.get_capabilities()
            ]
```

**File: `src/thoth/agents/factory.py`**
```python
"""
Agent Factory - Creates the standard set of agents from Thoth services.

This factory knows how to create agents from the existing services,
establishing the default agent ecosystem.
"""

from thoth.services.service_manager import ServiceManager
from thoth.agents.registry import AgentRegistry
from thoth.agents.adapters import ServiceAgentAdapter

def create_default_agents(service_manager: ServiceManager) -> AgentRegistry:
    """
    Create the standard set of agents from existing services.
    
    This function creates agents for all the major Thoth services,
    making their functionality available through the agent interface.
    
    Args:
        service_manager: The Thoth service manager instance
        
    Returns:
        Registry populated with default agents
    """
    registry = AgentRegistry()
    
    # Document Processing Agent
    # Handles OCR, text extraction, and content analysis
    registry.register("document_processor", ServiceAgentAdapter(
        service=service_manager.processing,
        capability_map={
            "ocr": "ocr_to_markdown",           # Convert PDF to markdown via OCR
            "analyze": "analyze_content",        # Analyze document content
            "extract_text": "extract_text",      # Extract plain text
            "process_pdf": "process_document"    # Full document processing
        },
        name="DocumentProcessor"
    ))
    
    # Citation Agent
    # Extracts and manages citations
    registry.register("citation_expert", ServiceAgentAdapter(
        service=service_manager.citation,
        capability_map={
            "extract_citations": "extract_citations",      # Extract from document
            "format_citations": "format_citations",        # Format in various styles
            "build_graph": "build_citation_graph",         # Create citation network
            "find_related": "find_related_papers"          # Find related works
        },
        name="CitationExpert"
    ))
    
    # Research Agent
    # Handles knowledge retrieval and search
    registry.register("research_analyst", ServiceAgentAdapter(
        service=service_manager.rag,
        capability_map={
            "search": "search",                    # Semantic search
            "index": "index_document",             # Add to knowledge base
            "query": "query_knowledge",            # Complex queries
            "find_similar": "find_similar_content" # Similarity search
        },
        name="ResearchAnalyst"
    ))
    
    # Discovery Agent
    # Finds new papers and monitors sources
    registry.register("paper_scout", ServiceAgentAdapter(
        service=service_manager.discovery,
        capability_map={
            "search_arxiv": "search_arxiv",              # Search arXiv
            "search_semantic": "search_semantic_scholar", # Search Semantic Scholar
            "monitor": "monitor_sources",                # Monitor for new papers
            "get_recommendations": "get_recommendations" # Get paper recommendations
        },
        name="PaperScout"
    ))
    
    # Note Generation Agent
    # Creates formatted notes for Obsidian
    registry.register("note_creator", ServiceAgentAdapter(
        service=service_manager.note,
        capability_map={
            "generate_note": "generate_note",          # Create note from analysis
            "format_markdown": "format_as_markdown",   # Format content as markdown
            "create_summary": "create_summary",        # Create paper summary
            "update_note": "update_existing_note"      # Update existing note
        },
        name="NoteCreator"
    ))
    
    # Web Search Agent
    # Performs web searches for additional context
    if hasattr(service_manager, 'web_search'):
        registry.register("web_researcher", ServiceAgentAdapter(
            service=service_manager.web_search,
            capability_map={
                "search_web": "search",                # General web search
                "search_scholarly": "search_scholarly", # Academic search
                "fact_check": "verify_claim",          # Fact checking
                "find_sources": "find_sources"         # Find primary sources
            },
            name="WebResearcher"
        ))
    
    return registry
```

#### Testing Requirements
```python
# tests/agents/test_registry.py
def test_registry_operations():
    """Test basic registry operations."""
    registry = AgentRegistry()
    mock_agent = Mock()
    mock_agent.get_capabilities.return_value = ["test"]
    
    # Register
    registry.register("test_agent", mock_agent)
    
    # Get
    retrieved = registry.get("test_agent")
    assert retrieved == mock_agent
    
    # List
    agents = registry.list_agents()
    assert len(agents) == 1
    assert agents[0]["name"] == "test_agent"
    
    # Find by capability
    found = registry.find_by_capability("test")
    assert "test_agent" in found

# tests/agents/test_factory.py
def test_factory_creates_default_agents():
    """Test that factory creates all expected agents."""
    mock_service_manager = Mock()
    # Mock all the services...
    
    registry = create_default_agents(mock_service_manager)
    
    agents = registry.list_agents()
    agent_names = [a["name"] for a in agents]
    
    assert "document_processor" in agent_names
    assert "citation_expert" in agent_names
    assert "research_analyst" in agent_names
```

#### Why This Matters
The registry provides a central place to discover what agents are available. The factory ensures that all of Thoth's existing services are immediately available as agents. This means on day one, users get a full suite of agents without any new service code.

---

## Phase 2: Core Orchestration (Still No User Impact)

### PR #4: Event Bus for Agent Communication
**Branch**: `feature/agent-event-bus`
**Size**: ~400 lines
**Duration**: 2-3 days
**Dependencies**: PR #1

#### Purpose
Create an event-driven communication system that allows agents and the orchestrator to communicate asynchronously. This enables monitoring, logging, and coordination without tight coupling.

#### What This Implements
An event bus is like a message board where agents can post updates about what they're doing. Other parts of the system can subscribe to these updates. This allows for:
- Real-time progress tracking
- Debugging and monitoring
- Loose coupling between components

#### Detailed Implementation

**File: `src/thoth/agents/events/bus.py`**
```python
"""
Event Bus - Asynchronous communication backbone for the agent system.

The event bus allows different parts of the agent system to communicate
without knowing about each other directly. It's like a public announcement
system where anyone can broadcast and anyone can listen.
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """
    An event that can be published on the bus.
    
    Events are immutable messages about things that have happened.
    """
    type: str                    # e.g., "task.started", "task.completed"
    data: Dict[str, Any]        # Event-specific data
    timestamp: datetime = None   # When the event occurred
    source: str = None          # What component emitted this event
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }

class EventBus:
    """
    Asynchronous event bus for agent communication.
    
    Example:
        bus = EventBus()
        
        # Subscribe to events
        async def on_task_complete(event):
            print(f"Task {event.data['task_id']} completed!")
        
        bus.subscribe("task.completed", on_task_complete)
        
        # Start the bus
        asyncio.create_task(bus.start())
        
        # Publish events
        await bus.publish("task.completed", {"task_id": "123", "result": "success"})
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize the event bus.
        
        Args:
            max_queue_size: Maximum number of events to queue
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._task = None
        
        # Event history for debugging
        self._history: List[Event] = []
        self._history_limit = 100
    
    def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """
        Subscribe to a specific event type.
        
        Args:
            event_type: The type of event to listen for (e.g., "task.started")
                       Use "*" to subscribe to all events
            handler: Async function to call when event occurs
        """
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Handler must be an async function, got {handler}")
        
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event type."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
    
    async def publish(
        self, 
        event_type: str, 
        data: Dict[str, Any], 
        source: str = None
    ) -> None:
        """
        Publish an event to the bus.
        
        Args:
            event_type: Type of event (e.g., "task.started")
            data: Event data
            source: Optional source identifier
        """
        event = Event(type=event_type, data=data, source=source)
        
        try:
            await self._queue.put(event)
        except asyncio.QueueFull:
            logger.error(f"Event queue full, dropping event: {event_type}")
    
    async def start(self) -> None:
        """
        Start processing events.
        
        This method runs forever, processing events from the queue
        and calling appropriate handlers.
        """
        self._running = True
        logger.info("Event bus started")
        
        while self._running:
            try:
                # Wait for next event with timeout
                event = await asyncio.wait_for(
                    self._queue.get(), 
                    timeout=1.0
                )
                
                # Add to history
                self._add_to_history(event)
                
                # Process event
                await self._process_event(event)
                
            except asyncio.TimeoutError:
                # No events, continue
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        logger.info("Event bus stopped")
    
    async def _process_event(self, event: Event) -> None:
        """Process a single event by calling all relevant handlers."""
        # Get handlers for this specific event type
        handlers = self._subscribers.get(event.type, [])
        
        # Also get universal handlers
        handlers.extend(self._subscribers.get("*", []))
        
        # Call all handlers concurrently
        if handlers:
            tasks = [
                self._call_handler(handler, event) 
                for handler in handlers
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _call_handler(self, handler: Callable, event: Event) -> None:
        """Call a single handler with error handling."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Handler {handler.__name__} failed for event {event.type}: {e}"
            )
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history for debugging."""
        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history.pop(0)
    
    def get_history(self, event_type: Optional[str] = None) -> List[Event]:
        """Get recent event history, optionally filtered by type."""
        if event_type:
            return [e for e in self._history if e.type == event_type]
        return list(self._history)
```

**File: `src/thoth/agents/events/handlers.py`**
```python
"""
Standard event handlers for common agent system events.
"""

import logging
from thoth.agents.events.bus import Event

logger = logging.getLogger(__name__)

class LoggingHandler:
    """Logs all events for debugging."""
    
    def __init__(self, level=logging.INFO):
        self.level = level
    
    async def __call__(self, event: Event):
        logger.log(
            self.level,
            f"[{event.source or 'Unknown'}] {event.type}: {event.data}"
        )

class MetricsHandler:
    """Collects metrics from events."""
    
    def __init__(self):
        self.task_count = 0
        self.success_count = 0
        self.failure_count = 0
    
    async def __call__(self, event: Event):
        if event.type == "task.started":
            self.task_count += 1
        elif event.type == "task.completed":
            if event.data.get("status") == "success":
                self.success_count += 1
            else:
                self.failure_count += 1
```

#### Testing Requirements
```python
# tests/agents/test_event_bus.py
async def test_event_publish_subscribe():
    """Test basic pub/sub functionality."""
    bus = EventBus()
    received_events = []
    
    async def handler(event):
        received_events.append(event)
    
    bus.subscribe("test.event", handler)
    
    # Start bus in background
    bus_task = asyncio.create_task(bus.start())
    
    # Publish event
    await bus.publish("test.event", {"message": "hello"})
    
    # Wait a bit for processing
    await asyncio.sleep(0.1)
    
    # Check event was received
    assert len(received_events) == 1
    assert received_events[0].data["message"] == "hello"
    
    await bus.stop()
    bus_task.cancel()

async def test_wildcard_subscription():
    """Test that * subscription receives all events."""
    bus = EventBus()
    all_events = []
    
    async def universal_handler(event):
        all_events.append(event)
    
    bus.subscribe("*", universal_handler)
    
    bus_task = asyncio.create_task(bus.start())
    
    await bus.publish("type.one", {"data": 1})
    await bus.publish("type.two", {"data": 2})
    
    await asyncio.sleep(0.1)
    
    assert len(all_events) == 2
    
    await bus.stop()
    bus_task.cancel()
```

#### Why This Matters
The event bus enables:
1. **Monitoring**: Track what agents are doing in real-time
2. **Debugging**: See the full history of what happened
3. **Integration**: Other systems can listen to agent events
4. **Decoupling**: Agents don't need to know who's listening

This becomes crucial when we add UI progress tracking, safety monitoring, and debugging tools.

---

### PR #5: Basic Orchestrator
**Branch**: `feature/agent-orchestrator`
**Size**: ~500 lines
**Duration**: 3 days
**Dependencies**: PRs #1-4

#### Purpose
Create the central orchestrator that coordinates agent execution. This is the "conductor" that manages the agent "orchestra", deciding which agents to use and when.

#### What This Implements
The orchestrator is responsible for:
- Receiving high-level tasks
- Determining which agent(s) should handle them
- Managing execution and collecting results
- Handling errors and retries

#### Detailed Implementation

**File: `src/thoth/agents/orchestrator.py`**
```python
"""
Agent Orchestrator - The conductor of the agent orchestra.

The orchestrator coordinates agent execution, managing task distribution,
monitoring progress, and handling failures. It's the brain that decides
which agents to use for which tasks.
"""

import asyncio
from typing import Dict, List, Optional, Any
from uuid import UUID
import logging

from thoth.agents.registry import AgentRegistry
from thoth.agents.events.bus import EventBus
from thoth.agents.schemas import Task, Result
from thoth.agents.exceptions import AgentError, AgentNotFoundError

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """
    Orchestrates agent execution for complex tasks.
    
    The orchestrator:
    1. Receives high-level tasks
    2. Determines which agent(s) should handle them
    3. Manages execution and monitors progress
    4. Handles failures and retries
    
    Example:
        orchestrator = AgentOrchestrator(registry, event_bus)
        
        # Single task execution
        task = Task(type="analyze", params={"text": "..."})
        result = await orchestrator.execute_task(task)
        
        # Workflow execution
        results = await orchestrator.execute_workflow([
            Task(type="ocr", params={"pdf": "paper.pdf"}),
            Task(type="extract_citations", params={"use_previous": True}),
            Task(type="generate_note", params={"use_previous": True})
        ])
    """
    
    def __init__(
        self, 
        registry: AgentRegistry, 
        event_bus: EventBus,
        max_concurrent_tasks: int = 5,
        task_timeout: float = 300.0  # 5 minutes default
    ):
        """
        Initialize the orchestrator.
        
        Args:
            registry: Agent registry for finding agents
            event_bus: Event bus for communication
            max_concurrent_tasks: Maximum tasks to run in parallel
            task_timeout: Default timeout for tasks in seconds
        """
        self.registry = registry
        self.event_bus = event_bus
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = task_timeout
        
        # Track running tasks
        self.running_tasks: Dict[UUID, asyncio.Task] = {}
        
        # Task results cache for workflows
        self.results_cache: Dict[UUID, Result] = {}
        
        # Semaphore for concurrent task limiting
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
    
    async def execute_task(
        self, 
        task: Task, 
        agent_name: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Result:
        """
        Execute a single task.
        
        Args:
            task: The task to execute
            agent_name: Specific agent to use (optional)
            timeout: Task-specific timeout (optional)
            
        Returns:
            The task result
            
        Raises:
            AgentNotFoundError: If specified agent doesn't exist
            AgentError: If no agent can handle the task
            TimeoutError: If task exceeds timeout
        """
        # Emit start event
        await self.event_bus.publish(
            "task.started",
            {"task_id": str(task.id), "type": task.type},
            source="orchestrator"
        )
        
        try:
            # Find appropriate agent
            if agent_name:
                agent = self.registry.get(agent_name)
            else:
                agent = self._find_agent_for_task(task)
            
            # Execute with timeout and concurrency control
            async with self.semaphore:
                # Store the running task
                task_coro = agent.execute(task)
                task_future = asyncio.create_task(task_coro)
                self.running_tasks[task.id] = task_future
                
                try:
                    # Execute with timeout
                    result = await asyncio.wait_for(
                        task_future,
                        timeout=timeout or self.task_timeout
                    )
                    
                    # Cache result for workflows
                    self.results_cache[task.id] = result
                    
                    # Emit completion event
                    await self.event_bus.publish(
                        "task.completed",
                        {
                            "task_id": str(task.id),
                            "status": result.status,
                            "execution_time": result.execution_time
                        },
                        source="orchestrator"
                    )
                    
                    return result
                    
                finally:
                    # Clean up
                    del self.running_tasks[task.id]
                    
        except asyncio.TimeoutError:
            # Emit timeout event
            await self.event_bus.publish(
                "task.timeout",
                {"task_id": str(task.id), "timeout": timeout or self.task_timeout},
                source="orchestrator"
            )
            raise TimeoutError(f"Task {task.id} timed out after {timeout or self.task_timeout}s")
            
        except Exception as e:
            # Emit failure event
            await self.event_bus.publish(
                "task.failed",
                {"task_id": str(task.id), "error": str(e)},
                source="orchestrator"
            )
            raise
    
    async def execute_workflow(
        self,
        tasks: List[Task],
        stop_on_failure: bool = True
    ) -> List[Result]:
        """
        Execute a workflow of tasks in sequence.
        
        Tasks can reference previous results using {"use_previous": True}
        in their parameters.
        
        Args:
            tasks: List of tasks to execute in order
            stop_on_failure: Whether to stop if a task fails
            
        Returns:
            List of results in the same order as tasks
        """
        results = []
        
        for i, task in enumerate(tasks):
            # Check if task wants to use previous result
            if task.params.get("use_previous") and i > 0:
                previous_result = results[-1]
                if previous_result.status == "success":
                    # Inject previous result data into task params
                    task.params.update({"previous_data": previous_result.data})
            
            try:
                result = await self.execute_task(task)
                results.append(result)
                
                if result.status == "failure" and stop_on_failure:
                    logger.warning(f"Workflow stopped due to task {task.id} failure")
                    break
                    
            except Exception as e:
                # Create failure result
                failure_result = Result(
                    task_id=task.id,
                    status="failure",
                    error=str(e)
                )
                results.append(failure_result)
                
                if stop_on_failure:
                    break
        
        return results
    
    async def execute_parallel(
        self,
        tasks: List[Task],
        return_exceptions: bool = False
    ) -> List[Result]:
        """
        Execute multiple tasks in parallel.
        
        Args:
            tasks: Tasks to execute concurrently
            return_exceptions: If True, exceptions are returned as failure results
            
        Returns:
            List of results in the same order as tasks
        """
        # Execute all tasks concurrently
        if return_exceptions:
            # Wrap each task to catch exceptions
            async def safe_execute(task):
                try:
                    return await self.execute_task(task)
                except Exception as e:
                    return Result(
                        task_id=task.id,
                        status="failure",
                        error=str(e)
                    )
            
            return await asyncio.gather(*[safe_execute(task) for task in tasks])
        else:
            return await asyncio.gather(*[self.execute_task(task) for task in tasks])
    
    def _find_agent_for_task(self, task: Task) -> Any:
        """
        Find an appropriate agent for a task type.
        
        This method implements the routing logic that determines
        which agent should handle which task type.
        """
        # First, check if any agent explicitly handles this task type
        agent_names = self.registry.find_by_capability(task.type)
        
        if not agent_names:
            # Try to infer from task type
            # This is where we can add smart routing logic
            if "ocr" in task.type or "pdf" in task.type:
                agent_names = ["document_processor"]
            elif "citation" in task.type:
                agent_names = ["citation_expert"]
            elif "search" in task.type or "research" in task.type:
                agent_names = ["research_analyst"]
            elif "note" in task.type:
                agent_names = ["note_creator"]
            else:
                raise AgentError(
                    f"No agent found for task type '{task.type}'. "
                    f"Available agents: {self.registry.list_agents()}"
                )
        
        # Use the first available agent
        # In the future, we could add load balancing here
        return self.registry.get(agent_names[0])
    
    async def shutdown(self):
        """Gracefully shutdown the orchestrator."""
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            logger.warning(f"Cancelling running task {task_id}")
            task.cancel()
        
        # Wait for all to complete
        if self.running_tasks:
            await asyncio.gather(
                *self.running_tasks.values(),
                return_exceptions=True
            )
```

**File: `src/thoth/agents/execution.py`**
```python
"""
Task execution strategies and helpers.
"""

from typing import List, Dict, Any
from thoth.agents.schemas import Task, Result

class ExecutionContext:
    """
    Context passed through workflow execution.
    
    This allows tasks to share data and state.
    """
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.results: List[Result] = []
    
    def add_result(self, result: Result):
        """Add a result to the context."""
        self.results.append(result)
        if result.status == "success" and result.data:
            # Make result data available by task type
            task = self._find_task_for_result(result)
            if task:
                self.data[task.type] = result.data
    
    def get_previous_data(self, task_type: str = None) -> Any:
        """Get data from previous task execution."""
        if task_type:
            return self.data.get(task_type)
        # Return the last successful result's data
        for result in reversed(self.results):
            if result.status == "success" and result.data:
                return result.data
        return None
```

#### Testing Requirements
```python
# tests/agents/test_orchestrator.py
async def test_single_task_execution():
    """Test executing a single task."""
    # Mock registry and agent
    mock_agent = AsyncMock()
    mock_agent.execute.return_value = Result(
        task_id=UUID("123"),
        status="success",
        data={"result": "done"}
    )
    
    registry = AgentRegistry()
    registry.register("test", mock_agent)
    
    # Create orchestrator
    bus = EventBus()
    orchestrator = AgentOrchestrator(registry, bus)
    
    # Execute task
    task = Task(type="test_task", params={"input": "data"})
    result = await orchestrator.execute_task(task, agent_name="test")
    
    assert result.status == "success"
    assert result.data["result"] == "done"
    mock_agent.execute.assert_called_once()

async def test_workflow_execution():
    """Test executing a workflow with data passing."""
    # Set up agents
    ocr_agent = AsyncMock()
    ocr_agent.execute.return_value = Result(
        task_id=UUID("1"),
        status="success", 
        data={"text": "extracted text"}
    )
    
    analysis_agent = AsyncMock()
    analysis_agent.execute.return_value = Result(
        task_id=UUID("2"),
        status="success",
        data={"summary": "analysis"}
    )
    
    registry = AgentRegistry()
    registry.register("ocr", ocr_agent)
    registry.register("analyzer", analysis_agent)
    
    # Create orchestrator
    bus = EventBus()
    orchestrator = AgentOrchestrator(registry, bus)
    
    # Execute workflow
    workflow = [
        Task(type="ocr", params={"pdf": "doc.pdf"}),
        Task(type="analyze", params={"use_previous": True})
    ]
    
    results = await orchestrator.execute_workflow(workflow)
    
    assert len(results) == 2
    assert all(r.status == "success" for r in results)
    
    # Check that second task received previous data
    second_call = analysis_agent.execute.call_args[0][0]
    assert "previous_data" in second_call.params
    assert second_call.params["previous_data"]["text"] == "extracted text"

async def test_parallel_execution():
    """Test parallel task execution."""
    # Create multiple mock agents
    agents = []
    for i in range(3):
        agent = AsyncMock()
        agent.execute.return_value = Result(
            task_id=UUID(str(i)),
            status="success",
            data={"agent": i}
        )
        agents.append(agent)
    
    registry = AgentRegistry()
    for i, agent in enumerate(agents):
        registry.register(f"agent_{i}", agent)
    
    bus = EventBus()
    orchestrator = AgentOrchestrator(registry, bus)
    
    # Execute tasks in parallel
    tasks = [
        Task(type=f"task_{i}", params={"data": i})
        for i in range(3)
    ]
    
    results = await orchestrator.execute_parallel(tasks)
    
    assert len(results) == 3
    assert all(r.status == "success" for r in results)
    
    # Verify all agents were called
    for agent in agents:
        agent.execute.assert_called_once()
```

#### Why This Matters
The orchestrator is the heart of the agent system. It provides:
1. **Task Routing**: Automatically finds the right agent for each task
2. **Workflow Support**: Chain tasks together with data passing
3. **Parallel Execution**: Run independent tasks concurrently
4. **Error Handling**: Graceful failure handling and recovery
5. **Monitoring**: Events for tracking execution progress

This enables complex workflows like "OCR this PDF, extract citations, then generate a note" to be expressed simply.

---

### PR #6: ServiceManager Extension
**Branch**: `feature/service-manager-agents`
**Size**: ~150 lines
**Duration**: 1 day
**Dependencies**: PRs #1-5

#### Purpose
Extend the existing ServiceManager to provide access to the agent system. This is the integration point that makes agents available throughout Thoth without modifying existing code.

#### What This Implements
Add two properties to ServiceManager:
- `agent_registry`: Access to available agents
- `agent_orchestrator`: Access to the orchestration system

These are lazy-loaded and only created if multi-agent mode is enabled.

#### Detailed Implementation

**File: `src/thoth/services/service_manager.py`** (modifications)
```python
# Add to imports
from typing import Optional

class ServiceManager:
    """
    Central manager for all Thoth services.
    
    [EXISTING DOCSTRING CONTENT...]
    
    Multi-Agent Support:
        When multi_agent is enabled in config, the service manager also provides
        access to the agent system through the agent_registry and agent_orchestrator
        properties.
    """
    
    def __init__(self, config: ThothConfig | None = None):
        """Initialize the ServiceManager."""
        # ... existing initialization code ...
        
        # Add agent system properties (lazy-loaded)
        self._agent_registry: Optional['AgentRegistry'] = None
        self._agent_orchestrator: Optional['AgentOrchestrator'] = None
        self._agent_event_bus: Optional['EventBus'] = None
    
    # ... all existing methods remain unchanged ...
    
    @property
    def agent_registry(self) -> Optional['AgentRegistry']:
        """
        Get the agent registry if multi-agent mode is enabled.
        
        Returns:
            AgentRegistry if enabled, None otherwise
            
        Example:
            if service_manager.agent_registry:
                agents = service_manager.agent_registry.list_agents()
        """
        # Check if multi-agent is enabled
        if not self.config.get('multi_agent', {}).get('enabled', False):
            return None
        
        # Lazy load the registry
        if self._agent_registry is None:
            from thoth.agents.factory import create_default_agents
            self._agent_registry = create_default_agents(self)
            self.logger.info(
                f"Initialized agent registry with {len(self._agent_registry.list_agents())} agents"
            )
        
        return self._agent_registry
    
    @property
    def agent_orchestrator(self) -> Optional['AgentOrchestrator']:
        """
        Get the agent orchestrator if multi-agent mode is enabled.
        
        Returns:
            AgentOrchestrator if enabled, None otherwise
            
        Example:
            if service_manager.agent_orchestrator:
                result = await service_manager.agent_orchestrator.execute_task(task)
        """
        # Check if multi-agent is enabled
        if not self.config.get('multi_agent', {}).get('enabled', False):
            return None
        
        # Need registry first
        if not self.agent_registry:
            return None
        
        # Lazy load the orchestrator
        if self._agent_orchestrator is None:
            # Create event bus first
            if self._agent_event_bus is None:
                from thoth.agents.events.bus import EventBus
                self._agent_event_bus = EventBus()
                
                # Start event bus in background
                asyncio.create_task(self._agent_event_bus.start())
                
                # Add standard handlers
                from thoth.agents.events.handlers import LoggingHandler
                self._agent_event_bus.subscribe("*", LoggingHandler())
            
            # Create orchestrator
            from thoth.agents.orchestrator import AgentOrchestrator
            self._agent_orchestrator = AgentOrchestrator(
                registry=self._agent_registry,
                event_bus=self._agent_event_bus,
                max_concurrent_tasks=self.config.get('multi_agent', {}).get(
                    'max_concurrent_tasks', 5
                ),
                task_timeout=self.config.get('multi_agent', {}).get(
                    'default_timeout', 300.0
                )
            )
            
            self.logger.info("Initialized agent orchestrator")
        
        return self._agent_orchestrator
    
    async def cleanup(self):
        """
        Clean up resources.
        
        [EXISTING DOCSTRING...]
        """
        # ... existing cleanup code ...
        
        # Clean up agent system if initialized
        if self._agent_orchestrator:
            await self._agent_orchestrator.shutdown()
        
        if self._agent_event_bus:
            await self._agent_event_bus.stop()
```

#### Testing Requirements
```python
# tests/test_service_manager_agents.py
def test_agent_properties_none_when_disabled():
    """Test that agent properties return None when multi-agent is disabled."""
    config = {"multi_agent": {"enabled": False}}
    manager = ServiceManager(config)
    
    assert manager.agent_registry is None
    assert manager.agent_orchestrator is None

def test_agent_properties_initialized_when_enabled():
    """Test that agent properties are initialized when enabled."""
    config = {"multi_agent": {"enabled": True}}
    manager = ServiceManager(config)
    
    # Mock the services that agents will wrap
    manager.processing = Mock()
    manager.citation = Mock()
    manager.rag = Mock()
    
    # Access registry
    registry = manager.agent_registry
    assert registry is not None
    
    # Should have default agents
    agents = registry.list_agents()
    assert len(agents) > 0
    
    # Access orchestrator
    orchestrator = manager.agent_orchestrator
    assert orchestrator is not None

def test_lazy_loading():
    """Test that agent systems are only created when accessed."""
    config = {"multi_agent": {"enabled": True}}
    manager = ServiceManager(config)
    
    # Nothing created yet
    assert manager._agent_registry is None
    assert manager._agent_orchestrator is None
    
    # Access registry - should create it
    registry = manager.agent_registry
    assert manager._agent_registry is not None
    assert manager._agent_orchestrator is None  # Still not created
    
    # Access orchestrator - should create it
    orchestrator = manager.agent_orchestrator
    assert manager._agent_orchestrator is not None
```

#### Why This Matters
This minimal change to ServiceManager:
1. Makes agents available throughout Thoth
2. Maintains backward compatibility (returns None when disabled)
3. Uses lazy loading for performance
4. Requires zero changes to existing code that uses ServiceManager

Any code that has access to ServiceManager can now optionally use agents:
```python
# Existing code continues to work
result = await service_manager.processing.ocr_to_markdown(pdf_path)

# New agent functionality available when enabled
if service_manager.agent_orchestrator:
    task = Task(type="ocr", params={"pdf_path": pdf_path})
    result = await service_manager.agent_orchestrator.execute_task(task)
```

---

## Phase 3: Pipeline Integration (Optional Features)

### PR #7: Pipeline Event Emission
**Branch**: `feature/pipeline-events`
**Size**: ~200 lines
**Duration**: 1 day
**Dependencies**: PR #4

#### Purpose
Add optional event emission to the existing pipeline so that when multi-agent mode is enabled, the pipeline can broadcast events about its progress. This enables agent monitoring without changing pipeline behavior.

#### What This Implements
Add event emission hooks to key pipeline methods. These events:
- Are only emitted when explicitly enabled
- Don't affect pipeline execution
- Allow agents to monitor pipeline progress

#### Detailed Implementation

**File: `src/thoth/pipeline.py`** (modifications)
```python
class ThothPipeline:
    """
    Main processing pipeline for Thoth.
    
    [EXISTING DOCSTRING...]
    
    Event Support:
        When emit_events=True is passed to the constructor, the pipeline will
        emit events to the provided event bus about processing progress. This
        allows external systems (like agents) to monitor pipeline execution.
    """
    
    def __init__(
        self,
        ocr_api_key: str | None = None,
        llm_api_key: str | None = None,
        templates_dir: Path | None = None,
        prompts_dir: Path | None = None,
        output_dir: Path | None = None,
        notes_dir: Path | None = None,
        config: dict[str, Any] | None = None,
        service_manager: ServiceManager | None = None,
        emit_events: bool = False,  # NEW PARAMETER
        event_bus: Optional['EventBus'] = None  # NEW PARAMETER
    ):
        """
        Initialize the pipeline.
        
        [EXISTING DOCSTRING...]
        
        Args:
            [EXISTING ARGS...]
            emit_events: Whether to emit progress events
            event_bus: Event bus to emit events to (required if emit_events=True)
        """
        # ... existing initialization ...
        
        # Event emission setup
        self.emit_events = emit_events
        self._event_bus = event_bus
        
        if emit_events and not event_bus:
            self.logger.warning(
                "emit_events=True but no event_bus provided. Events will not be emitted."
            )
            self.emit_events = False
    
    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Emit an event if event emission is enabled.
        
        This is a no-op if emit_events is False or no event bus is available.
        
        Args:
            event_type: Type of event (e.g., "pipeline.pdf.started")
            data: Event data
        """
        if self.emit_events and self._event_bus:
            try:
                await self._event_bus.publish(
                    event_type,
                    data,
                    source="pipeline"
                )
            except Exception as e:
                # Don't let event emission failures affect pipeline
                self.logger.debug(f"Failed to emit event {event_type}: {e}")
    
    async def process_pdf(
        self,
        pdf_path: str | Path,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> tuple[Path, Path, Path]:
        """
        Process a PDF through OCR, analysis, citation extraction and note generation.
        
        [EXISTING DOCSTRING...]
        """
        pdf_path = Path(pdf_path)
        
        # Emit start event
        await self._emit_event(
            "pipeline.pdf.started",
            {
                "pdf_path": str(pdf_path),
                "pdf_name": pdf_path.name,
                "use_cache": use_cache
            }
        )
        
        try:
            # Check cache first
            if use_cache and self._is_processed(pdf_path):
                self.logger.info(f"Using cached results for {pdf_path.name}")
                
                await self._emit_event(
                    "pipeline.pdf.cache_hit",
                    {"pdf_path": str(pdf_path)}
                )
                
                return self._get_cached_results(pdf_path)
            
            # === EXISTING PROCESSING LOGIC UNCHANGED ===
            
            # Step 1: OCR Processing
            await self._emit_event(
                "pipeline.pdf.ocr_started",
                {"pdf_path": str(pdf_path)}
            )
            
            markdown_path = await self._ocr_pdf(pdf_path)
            
            await self._emit_event(
                "pipeline.pdf.ocr_completed",
                {
                    "pdf_path": str(pdf_path),
                    "markdown_path": str(markdown_path)
                }
            )
            
            # Step 2: Content Analysis
            await self._emit_event(
                "pipeline.pdf.analysis_started",
                {"pdf_path": str(pdf_path)}
            )
            
            analysis = await self._analyze_content(markdown_path)
            
            await self._emit_event(
                "pipeline.pdf.analysis_completed",
                {
                    "pdf_path": str(pdf_path),
                    "has_citations": len(analysis.citations) > 0
                }
            )
            
            # Step 3: Citation Processing
            if analysis.citations:
                await self._emit_event(
                    "pipeline.pdf.citations_started",
                    {
                        "pdf_path": str(pdf_path),
                        "citation_count": len(analysis.citations)
                    }
                )
                
                await self._process_citations(analysis.citations, pdf_path)
                
                await self._emit_event(
                    "pipeline.pdf.citations_completed",
                    {"pdf_path": str(pdf_path)}
                )
            
            # Step 4: Note Generation
            await self._emit_event(
                "pipeline.pdf.note_started",
                {"pdf_path": str(pdf_path)}
            )
            
            note_path = await self._generate_note(analysis, pdf_path)
            
            await self._emit_event(
                "pipeline.pdf.note_completed",
                {
                    "pdf_path": str(pdf_path),
                    "note_path": str(note_path)
                }
            )
            
            # Step 5: RAG Indexing
            await self._emit_event(
                "pipeline.pdf.indexing_started",
                {"pdf_path": str(pdf_path)}
            )
            
            await self._index_content(analysis, pdf_path)
            
            await self._emit_event(
                "pipeline.pdf.indexing_completed",
                {"pdf_path": str(pdf_path)}
            )
            
            # Cache results
            analysis_path = self._save_analysis(analysis, pdf_path)
            
            # Emit completion event
            await self._emit_event(
                "pipeline.pdf.completed",
                {
                    "pdf_path": str(pdf_path),
                    "markdown_path": str(markdown_path),
                    "analysis_path": str(analysis_path),
                    "note_path": str(note_path),
                    "duration": time.time() - start_time  # If start_time tracked
                }
            )
            
            return markdown_path, analysis_path, note_path
            
        except Exception as e:
            # Emit error event
            await self._emit_event(
                "pipeline.pdf.failed",
                {
                    "pdf_path": str(pdf_path),
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    # Similar event emission can be added to other pipeline methods like:
    # - process_batch()
    # - process_url()
    # - monitor_folder()
```

**File: `src/thoth/pipelines/base.py`** (modifications)
```python
class BasePipeline(ABC):
    """
    Abstract base class for all pipelines.
    
    [EXISTING DOCSTRING...]
    """
    
    def __init__(self, *args, emit_events: bool = False, event_bus=None, **kwargs):
        """Initialize base pipeline with optional event support."""
        # ... existing initialization ...
        
        self.emit_events = emit_events
        self._event_bus = event_bus
    
    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event if enabled (inherited by all pipelines)."""
        if self.emit_events and self._event_bus:
            try:
                await self._event_bus.publish(event_type, data, source=self.__class__.__name__)
            except Exception:
                pass  # Never let events break pipeline
```

#### Testing Requirements
```python
# tests/test_pipeline_events.py
async def test_pipeline_emits_events_when_enabled():
    """Test that pipeline emits events when enabled."""
    # Create event bus and track events
    event_bus = EventBus()
    received_events = []
    
    async def event_handler(event):
        received_events.append(event)
    
    event_bus.subscribe("*", event_handler)
    asyncio.create_task(event_bus.start())
    
    # Create pipeline with events enabled
    pipeline = ThothPipeline(
        service_manager=mock_service_manager,
        emit_events=True,
        event_bus=event_bus
    )
    
    # Process a PDF
    await pipeline.process_pdf("test.pdf")
    
    # Wait for events
    await asyncio.sleep(0.1)
    
    # Check events were emitted
    event_types = [e.type for e in received_events]
    assert "pipeline.pdf.started" in event_types
    assert "pipeline.pdf.completed" in event_types

async def test_pipeline_no_events_when_disabled():
    """Test that pipeline doesn't emit events when disabled."""
    event_bus = EventBus()
    received_events = []
    
    async def event_handler(event):
        received_events.append(event)
    
    event_bus.subscribe("*", event_handler)
    asyncio.create_task(event_bus.start())
    
    # Create pipeline with events disabled (default)
    pipeline = ThothPipeline(service_manager=mock_service_manager)
    
    # Process a PDF
    await pipeline.process_pdf("test.pdf")
    
    # Wait a bit
    await asyncio.sleep(0.1)
    
    # No events should be received
    assert len(received_events) == 0

def test_pipeline_works_without_event_bus():
    """Test that pipeline works normally even if event bus not provided."""
    pipeline = ThothPipeline(
        service_manager=mock_service_manager,
        emit_events=True  # Enabled but no bus
    )
    
    # Should work fine, just no events
    result = await pipeline.process_pdf("test.pdf")
    assert result is not None
```

#### Why This Matters
Event emission enables:
1. **Progress Tracking**: Monitor pipeline execution in real-time
2. **Integration**: Agents can listen to pipeline events
3. **Debugging**: See exactly what the pipeline is doing
4. **No Impact**: When disabled, zero performance overhead
5. **Metrics**: Collect timing and success/failure stats

This becomes the foundation for UI progress bars, agent monitoring, and system observability.

---

### PR #8: Configuration Schema Update
**Branch**: `feature/agent-config`
**Size**: ~100 lines
**Duration**: 1 day
**Dependencies**: None

#### Purpose
Add the multi-agent configuration schema to Thoth's configuration system. This defines all the settings users can configure for the agent system.

#### What This Implements
- Configuration schema for multi-agent settings
- Validation of configuration values
- Default values that ensure backward compatibility

#### Detailed Implementation

**File: `src/thoth/config/schema.py`** (new sections)
```python
"""
Configuration schema definitions.

[EXISTING FILE CONTENT...]
"""

from pydantic import BaseModel, Field, validator
from typing import Literal, Optional

class MultiAgentConfig(BaseModel):
    """
    Configuration for the multi-agent system.
    
    All settings have safe defaults that keep the system disabled
    until explicitly enabled by the user.
    """
    
    # Core settings
    enabled: bool = Field(
        default=False,
        description="Enable the multi-agent system. Default: False for backward compatibility"
    )
    
    orchestrator_mode: Literal["in_process", "distributed"] = Field(
        default="in_process",
        description="How to run agents. 'in_process' runs locally, 'distributed' requires additional setup"
    )
    
    # Resource limits
    max_concurrent_agents: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of agents that can run concurrently"
    )
    
    max_tasks_per_agent: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum tasks a single agent can handle concurrently"
    )
    
    default_task_timeout: float = Field(
        default=300.0,
        ge=10.0,
        le=3600.0,
        description="Default timeout for agent tasks in seconds (5 minutes default)"
    )
    
    # Feature flags
    enable_agent_creation: bool = Field(
        default=False,
        description="Allow dynamic creation of new agents. Requires safety level 'moderate' or 'permissive'"
    )
    
    enable_phoenix_pattern: bool = Field(
        default=False,
        description="Enable self-modifying agent capabilities (experimental)"
    )
    
    emit_pipeline_events: bool = Field(
        default=True,
        description="Emit events from pipeline when agent mode is enabled"
    )
    
    # Safety settings
    safety_level: Literal["strict", "moderate", "permissive"] = Field(
        default="strict",
        description="""
        Safety level for agent operations:
        - strict: No file modifications, no agent creation, require approval
        - moderate: Allow approved modifications, agent creation with validation
        - permissive: Allow most operations (use with caution)
        """
    )
    
    require_approval_for_writes: bool = Field(
        default=True,
        description="Require user approval before agents can write/modify files"
    )
    
    enable_rollback: bool = Field(
        default=True,
        description="Enable automatic rollback of failed agent operations"
    )
    
    # Monitoring settings
    log_agent_actions: bool = Field(
        default=True,
        description="Log all agent actions for audit trail"
    )
    
    metrics_enabled: bool = Field(
        default=True,
        description="Collect metrics on agent performance"
    )
    
    event_history_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Number of events to keep in history for debugging"
    )
    
    @validator('enable_agent_creation')
    def validate_agent_creation(cls, v, values):
        """Ensure agent creation is only enabled with appropriate safety level."""
        if v and values.get('safety_level') == 'strict':
            raise ValueError(
                "Agent creation requires safety_level 'moderate' or 'permissive'"
            )
        return v
    
    @validator('enable_phoenix_pattern')
    def validate_phoenix_pattern(cls, v, values):
        """Ensure Phoenix pattern is only enabled with appropriate settings."""
        if v:
            if not values.get('enable_agent_creation'):
                raise ValueError(
                    "Phoenix pattern requires enable_agent_creation=True"
                )
            if values.get('safety_level') == 'strict':
                raise ValueError(
                    "Phoenix pattern requires safety_level 'moderate' or 'permissive'"
                )
        return v

# Update main config
class ThothConfig(BaseModel):
    """
    Main Thoth configuration.
    
    [EXISTING DOCSTRING...]
    """
    
    # ... existing fields ...
    
    # Multi-agent configuration
    multi_agent: MultiAgentConfig = Field(
        default_factory=MultiAgentConfig,
        description="Multi-agent system configuration"
    )
```

**File: `src/thoth/utilities/config.py`** (modifications)
```python
def get_config() -> dict:
    """
    Get Thoth configuration from file and environment.
    
    [EXISTING DOCSTRING...]
    
    Multi-Agent Configuration:
        The multi_agent section controls the agent system. By default,
        it's completely disabled for backward compatibility.
    """
    # ... existing config loading ...
    
    # Ensure multi_agent section exists with defaults
    if 'multi_agent' not in config:
        config['multi_agent'] = {}
    
    # Apply environment variable overrides for multi-agent
    # THOTH_MULTI_AGENT_ENABLED=true
    if env_enabled := os.getenv('THOTH_MULTI_AGENT_ENABLED'):
        config['multi_agent']['enabled'] = env_enabled.lower() == 'true'
    
    # THOTH_MULTI_AGENT_SAFETY_LEVEL=moderate
    if safety_level := os.getenv('THOTH_MULTI_AGENT_SAFETY_LEVEL'):
        config['multi_agent']['safety_level'] = safety_level
    
    return config
```

**Example Configuration File**:
```toml
# ~/.thoth.toml

# Existing configuration remains unchanged
[processing]
ocr_service = "mistral"

[llm]
model = "claude-3"

# New multi-agent section (optional)
[multi_agent]
# Everything disabled by default
enabled = false

# When you're ready to try agents:
# enabled = true
# safety_level = "moderate"
# enable_agent_creation = true

# Resource limits
# max_concurrent_agents = 5
# default_task_timeout = 300

# Safety settings
# require_approval_for_writes = true
# enable_rollback = true
```

#### Testing Requirements
```python
# tests/test_agent_config.py
def test_default_config_disables_agents():
    """Test that default configuration has agents disabled."""
    config = MultiAgentConfig()
    
    assert config.enabled is False
    assert config.safety_level == "strict"
    assert config.enable_agent_creation is False

def test_config_validation():
    """Test configuration validation rules."""
    # Can't enable agent creation with strict safety
    with pytest.raises(ValueError, match="safety_level"):
        MultiAgentConfig(
            enable_agent_creation=True,
            safety_level="strict"
        )
    
    # Phoenix pattern requires agent creation
    with pytest.raises(ValueError, match="enable_agent_creation"):
        MultiAgentConfig(
            enable_phoenix_pattern=True,
            enable_agent_creation=False
        )

def test_environment_override():
    """Test that environment variables override config."""
    os.environ['THOTH_MULTI_AGENT_ENABLED'] = 'true'
    
    config = get_config()
    
    assert config['multi_agent']['enabled'] is True
```

#### Why This Matters
The configuration schema:
1. **Ensures Safety**: Strict defaults keep system safe
2. **Enables Gradual Adoption**: Users can enable features one by one
3. **Validates Settings**: Prevents invalid configurations
4. **Documents Options**: Clear descriptions of what each setting does
5. **Environment Support**: Can be controlled via environment variables

This gives users full control over the agent system while maintaining safety and backward compatibility.

---

## Phase 4: API Extensions

### PR #9: Agent Router (New Endpoints)
**Branch**: `feature/agent-api`
**Size**: ~600 lines
**Duration**: 3 days
**Dependencies**: PRs #1-8

#### Purpose
Create new API endpoints for interacting with the agent system. These endpoints allow external clients (like the Obsidian plugin) to list agents, execute tasks, and monitor progress.

#### What This Implements
New `/api/v2/agents` endpoints for:
- Listing available agents
- Executing tasks
- Monitoring execution status
- Getting agent capabilities

#### Detailed Implementation

**File: `src/thoth/server/routers/agents.py`** (new file)
```python
"""
Agent API endpoints.

This router provides HTTP API access to the agent system, allowing
external clients to interact with agents.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from uuid import UUID
import asyncio
import json

from thoth.agents.schemas import Task, Result
from thoth.agents.exceptions import AgentNotFoundError, AgentError
from thoth.server.dependencies import get_service_manager
from thoth.services.service_manager import ServiceManager
from pydantic import BaseModel, Field

# Request/Response models
class AgentInfo(BaseModel):
    """Information about an available agent."""
    name: str
    type: str
    capabilities: List[str]
    description: Optional[str] = None

class TaskRequest(BaseModel):
    """Request to execute a task."""
    type: str = Field(description="Type of task to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    agent: Optional[str] = Field(None, description="Specific agent to use")
    timeout: Optional[float] = Field(None, description="Task timeout in seconds")

class TaskResponse(BaseModel):
    """Response from task execution."""
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

class WorkflowRequest(BaseModel):
    """Request to execute a workflow."""
    tasks: List[TaskRequest]
    stop_on_failure: bool = True
    parallel: bool = False

# Create router
router = APIRouter(
    prefix="/api/v2/agents",
    tags=["agents"],
    responses={
        404: {"description": "Multi-agent system not enabled"},
        403: {"description": "Operation not permitted with current safety level"}
    }
)

@router.get("/", response_model=List[AgentInfo])
async def list_agents(
    service_manager: ServiceManager = Depends(get_service_manager)
) -> List[AgentInfo]:
    """
    List all available agents.
    
    Returns a list of agents with their capabilities. This endpoint
    helps clients discover what agents are available and what they can do.
    """
    if not service_manager.agent_registry:
        raise HTTPException(
            status_code=404,
            detail="Multi-agent system is not enabled. Set multi_agent.enabled=true in configuration."
        )
    
    agents = service_manager.agent_registry.list_agents()
    
    return [
        AgentInfo(
            name=agent["name"],
            type=agent["type"],
            capabilities=agent["capabilities"],
            description=f"Agent that can: {', '.join(agent['capabilities'])}"
        )
        for agent in agents
    ]

@router.get("/{agent_name}/capabilities")
async def get_agent_capabilities(
    agent_name: str,
    service_manager: ServiceManager = Depends(get_service_manager)
) -> Dict[str, Any]:
    """
    Get detailed capabilities of a specific agent.
    
    This provides more detailed information about what an agent can do,
    including parameter schemas for each capability.
    """
    if not service_manager.agent_registry:
        raise HTTPException(status_code=404, detail="Multi-agent system not enabled")
    
    try:
        agent = service_manager.agent_registry.get(agent_name)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    # In the future, we could introspect the service methods to provide
    # parameter schemas. For now, return basic capability list.
    return {
        "name": agent_name,
        "capabilities": agent.get_capabilities(),
        "timeout": service_manager.config.multi_agent.default_task_timeout,
        "concurrent_tasks": service_manager.config.multi_agent.max_tasks_per_agent
    }

@router.post("/execute", response_model=TaskResponse)
async def execute_task(
    request: TaskRequest,
    service_manager: ServiceManager = Depends(get_service_manager)
) -> TaskResponse:
    """
    Execute a single task.
    
    This endpoint executes a task and returns the result. For long-running
    tasks, consider using the streaming endpoint instead.
    """
    if not service_manager.agent_orchestrator:
        raise HTTPException(status_code=404, detail="Agent orchestrator not available")
    
    # Create task from request
    task = Task(
        type=request.type,
        params=request.params,
        metadata={"api_request": True}
    )
    
    try:
        # Execute task
        result = await service_manager.agent_orchestrator.execute_task(
            task,
            agent_name=request.agent,
            timeout=request.timeout
        )
        
        return TaskResponse(
            task_id=str(task.id),
            status=result.status,
            result=result.data,
            error=result.error,
            execution_time=result.execution_time
        )
        
    except TimeoutError:
        return TaskResponse(
            task_id=str(task.id),
            status="timeout",
            error=f"Task timed out after {request.timeout or service_manager.config.multi_agent.default_task_timeout} seconds"
        )
    except AgentError as e:
        return TaskResponse(
            task_id=str(task.id),
            status="error",
            error=str(e)
        )
    except Exception as e:
        # Log unexpected errors
        service_manager.logger.error(f"Unexpected error executing task: {e}")
        return TaskResponse(
            task_id=str(task.id),
            status="error",
            error="Internal server error"
        )

@router.post("/execute/stream")
async def execute_task_streaming(
    request: TaskRequest,
    service_manager: ServiceManager = Depends(get_service_manager)
):
    """
    Execute a task with streaming updates.
    
    This endpoint returns a stream of Server-Sent Events (SSE) that
    provide real-time updates on task execution progress.
    """
    if not service_manager.agent_orchestrator:
        raise HTTPException(status_code=404, detail="Agent orchestrator not available")
    
    async def event_stream():
        """Generate SSE stream of task execution events."""
        # Create task
        task = Task(
            type=request.type,
            params=request.params,
            metadata={"api_request": True, "streaming": True}
        )
        
        # Subscribe to events for this task
        received_events = []
        task_complete = asyncio.Event()
        
        async def task_event_handler(event):
            if event.data.get("task_id") == str(task.id):
                received_events.append(event)
                if event.type in ["task.completed", "task.failed", "task.timeout"]:
                    task_complete.set()
        
        # Subscribe to task events
        event_bus = service_manager._agent_event_bus
        if event_bus:
            event_bus.subscribe("task.*", task_event_handler)
        
        # Start task execution in background
        execute_task = asyncio.create_task(
            service_manager.agent_orchestrator.execute_task(
                task,
                agent_name=request.agent,
                timeout=request.timeout
            )
        )
        
        # Send initial event
        yield f"data: {json.dumps({'type': 'task.created', 'task_id': str(task.id)})}\n\n"
        
        # Stream events as they arrive
        last_index = 0
        while not task_complete.is_set() or last_index < len(received_events):
            # Send any new events
            while last_index < len(received_events):
                event = received_events[last_index]
                event_data = {
                    "type": event.type,
                    "timestamp": event.timestamp.isoformat(),
                    **event.data
                }
                yield f"data: {json.dumps(event_data)}\n\n"
                last_index += 1
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
        
        # Get final result
        try:
            result = await execute_task
            final_data = {
                "type": "task.result",
                "task_id": str(task.id),
                "status": result.status,
                "result": result.data,
                "error": result.error,
                "execution_time": result.execution_time
            }
            yield f"data: {json.dumps(final_data)}\n\n"
        except Exception as e:
            error_data = {
                "type": "task.error",
                "task_id": str(task.id),
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        
        # Cleanup
        if event_bus:
            event_bus.unsubscribe("task.*", task_event_handler)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@router.post("/workflow", response_model=List[TaskResponse])
async def execute_workflow(
    request: WorkflowRequest,
    service_manager: ServiceManager = Depends(get_service_manager)
) -> List[TaskResponse]:
    """
    Execute a workflow of multiple tasks.
    
    Tasks can be executed sequentially (default) or in parallel.
    In sequential mode, tasks can reference results from previous tasks.
    """
    if not service_manager.agent_orchestrator:
        raise HTTPException(status_code=404, detail="Agent orchestrator not available")
    
    # Convert requests to tasks
    tasks = [
        Task(
            type=task_req.type,
            params=task_req.params,
            metadata={"agent": task_req.agent} if task_req.agent else {}
        )
        for task_req in request.tasks
    ]
    
    try:
        # Execute workflow
        if request.parallel:
            results = await service_manager.agent_orchestrator.execute_parallel(
                tasks,
                return_exceptions=True
            )
        else:
            results = await service_manager.agent_orchestrator.execute_workflow(
                tasks,
                stop_on_failure=request.stop_on_failure
            )
        
        # Convert results to responses
        return [
            TaskResponse(
                task_id=str(result.task_id),
                status=result.status,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time
            )
            for result in results
        ]
        
    except Exception as e:
        service_manager.logger.error(f"Workflow execution failed: {e}")
        raise HTTPException(status_code=500, detail="Workflow execution failed")

@router.get("/events/history")
async def get_event_history(
    event_type: Optional[str] = None,
    limit: int = 100,
    service_manager: ServiceManager = Depends(get_service_manager)
) -> List[Dict[str, Any]]:
    """
    Get recent event history for debugging.
    
    This endpoint returns recent events from the agent system,
    useful for debugging and monitoring.
    """
    if not service_manager._agent_event_bus:
        raise HTTPException(status_code=404, detail="Event bus not available")
    
    # Get events from history
    events = service_manager._agent_event_bus.get_history(event_type)
    
    # Limit results
    events = events[-limit:]
    
    # Convert to JSON-serializable format
    return [
        {
            "type": event.type,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source,
            "data": event.data
        }
        for event in events
    ]

# Health check endpoint
@router.get("/health")
async def agent_health(
    service_manager: ServiceManager = Depends(get_service_manager)
) -> Dict[str, Any]:
    """Check health of the agent system."""
    return {
        "enabled": service_manager.agent_registry is not None,
        "agents_available": len(service_manager.agent_registry.list_agents()) if service_manager.agent_registry else 0,
        "orchestrator_ready": service_manager.agent_orchestrator is not None,
        "event_bus_active": service_manager._agent_event_bus is not None and service_manager._agent_event_bus._running if service_manager._agent_event_bus else False
    }
```

**File: `src/thoth/server/app.py`** (modifications)
```python
def create_app(config: Optional[Dict] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    [EXISTING DOCSTRING...]
    """
    # ... existing app creation ...
    
    # Include routers
    app.include_router(health.router)
    app.include_router(operations.router)
    app.include_router(tools.router)
    app.include_router(config_router.router)
    app.include_router(chat.router)
    app.include_router(research.router)
    app.include_router(websocket.router)
    
    # Include agent router if multi-agent is enabled
    if config and config.get('multi_agent', {}).get('enabled', False):
        from thoth.server.routers import agents
        app.include_router(agents.router)
        logger.info("Multi-agent API endpoints enabled")
    
    return app
```

#### Testing Requirements
```python
# tests/server/test_agent_api.py
async def test_list_agents_disabled():
    """Test that agent endpoints return 404 when disabled."""
    app = create_app({"multi_agent": {"enabled": False}})
    client = TestClient(app)
    
    response = client.get("/api/v2/agents/")
    assert response.status_code == 404

async def test_list_agents_enabled():
    """Test listing agents when enabled."""
    app = create_app({"multi_agent": {"enabled": True}})
    client = TestClient(app)
    
    response = client.get("/api/v2/agents/")
    assert response.status_code == 200
    
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) > 0
    
    # Check agent structure
    agent = agents[0]
    assert "name" in agent
    assert "capabilities" in agent

async def test_execute_task():
    """Test task execution via API."""
    app = create_app({"multi_agent": {"enabled": True}})
    client = TestClient(app)
    
    # Execute a simple task
    response = client.post("/api/v2/agents/execute", json={
        "type": "test_task",
        "params": {"input": "test"},
        "agent": "test_agent"
    })
    
    assert response.status_code == 200
    result = response.json()
    assert "task_id" in result
    assert "status" in result

async def test_streaming_endpoint():
    """Test SSE streaming endpoint."""
    app = create_app({"multi_agent": {"enabled": True}})
    client = TestClient(app)
    
    # Execute streaming task
    with client.stream("POST", "/api/v2/agents/execute/stream", json={
        "type": "long_task",
        "params": {"duration": 1}
    }) as response:
        events = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        
        # Should have multiple events
        assert len(events) > 1
        assert events[0]["type"] == "task.created"
        assert events[-1]["type"] == "task.result"
```

#### Why This Matters
The API endpoints enable:
1. **External Integration**: Any client can use agents via HTTP
2. **Progress Monitoring**: SSE streaming for real-time updates
3. **Workflow Support**: Execute complex multi-step operations
4. **Discovery**: Clients can discover available agents
5. **Debugging**: Event history for troubleshooting

This API becomes the primary interface for the Obsidian plugin and any other clients to interact with the agent system.

---

## Continue to Phase 5-8...

[The document would continue with similar detail for:
- Phase 5: Dynamic Agent Creation
- Phase 6: Safety Framework  
- Phase 7: Obsidian Plugin Integration
- Phase 8: Advanced Features

Each PR would have the same level of detail explaining:
- Purpose
- What it implements
- Detailed code with extensive comments
- Testing requirements
- Why it matters]

Would you like me to continue with the remaining phases?
## Phase 5: Dynamic Agent Creation

### PR #10: Agent Builder Core
**Branch**: `feature/agent-builder`
**Size**: ~800 lines
**Duration**: 4-5 days
**Dependencies**: PRs #1-9

#### Purpose
Implement the core system for creating new agents dynamically. This allows users to describe what they want an agent to do in natural language, and the system creates an appropriate agent by composing existing services.

#### What This Implements
The agent builder is like a "agent factory" that:
- Understands natural language descriptions
- Maps requirements to existing service capabilities
- Generates appropriate prompts and configurations
- Creates new agents without writing code

This is the foundation for the "Claude Code-like" experience where users can create custom agents through conversation.

#### Why This Matters
Dynamic agent creation transforms Thoth from a system with fixed agents to one where users can create exactly the agents they need for their specific research workflows. It democratizes agent creation - no programming required.

---

## Phase 6: Safety Framework

### PR #12: Agent Safety Layer
**Branch**: `feature/agent-safety`
**Size**: ~1000 lines
**Duration**: 5 days
**Dependencies**: PRs #1-9

#### Purpose
Implement comprehensive safety measures to ensure agents cannot harm user data or system stability. This includes validation, monitoring, rollback capabilities, and constitutional AI principles.

#### What This Implements
A multi-layered safety system:
- **Permission System**: What agents can and cannot do
- **Validation Layer**: Check all inputs and outputs
- **Monitoring**: Real-time behavior tracking
- **Rollback**: Undo any agent action
- **Constitution**: Core principles agents must follow

#### Why This Matters
Safety is paramount when giving agents the ability to perform actions autonomously. This framework ensures that even if an agent malfunctions or receives malicious input, user data remains safe and all actions can be reversed.

---

## Phase 7: Obsidian Plugin Integration

### PR #14: Agent Types and API Client
**Branch**: `feature/obsidian-agent-types`
**Size**: ~400 lines
**Duration**: 2 days
**Dependencies**: PR #9 (API endpoints)

#### Purpose
Add TypeScript types and API client code to the Obsidian plugin to enable communication with the agent system. This creates the foundation for all agent-related UI features.

#### What This Implements
- TypeScript interfaces for agents, tasks, and results
- API client class for communicating with agent endpoints
- Error handling and retry logic
- Event streaming support for real-time updates

#### Why This Matters
This creates the bridge between the Obsidian UI and the Python agent backend. It ensures type safety and provides a clean API for the UI components to use.

---

## Implementation Best Practices

### Code Organization
1. **Each PR should be self-contained**: Include implementation, tests, and docs
2. **Follow existing patterns**: Match Thoth's code style and conventions
3. **Comprehensive docstrings**: Every class and method should be documented
4. **Type hints everywhere**: Use Python type hints for clarity

### Testing Strategy
1. **Unit tests for each component**: Minimum 90% coverage
2. **Integration tests for workflows**: Test agent interactions
3. **API tests**: Test all endpoints with various scenarios
4. **Safety tests**: Verify safety measures work correctly

### Documentation Requirements
1. **Update user docs**: How to use new features
2. **API documentation**: OpenAPI schemas for new endpoints
3. **Architecture docs**: Update system diagrams
4. **Migration guides**: Help users adopt new features

### Review Process
1. **Two reviewers minimum**: One for code, one for architecture
2. **Security review**: For agent creation and safety features
3. **Performance testing**: Ensure no degradation
4. **User experience review**: For UI changes

---

## Risk Mitigation Strategies

### Technical Risks
1. **Performance Impact**
   - Mitigation: Lazy loading, feature flags, performance benchmarks
   
2. **Breaking Changes**
   - Mitigation: Extensive testing, gradual rollout, backward compatibility

3. **Security Vulnerabilities**
   - Mitigation: Security review, sandboxing, permission system

### User Experience Risks
1. **Complexity**
   - Mitigation: Progressive disclosure, good defaults, clear documentation
   
2. **Confusion with Existing Features**
   - Mitigation: Clear naming, separate UI sections, migration guides

### Operational Risks
1. **Rollout Issues**
   - Mitigation: Feature flags, staged rollout, monitoring
   
2. **Support Burden**
   - Mitigation: Comprehensive docs, self-service tools, clear error messages

---

## Success Metrics

### Technical Metrics
- All tests passing (100%)
- No performance regression (±5%)
- Zero security vulnerabilities
- Code coverage >90%

### User Metrics
- Feature adoption rate
- User-created agents count
- Task success rate
- Time to create first agent

### Business Metrics
- User satisfaction scores
- Support ticket volume
- Feature usage analytics
- Community contributions

---

## Conclusion

This detailed implementation plan provides a clear path from the current Thoth system to a powerful multi-agent platform. By following this PR-by-PR approach:

1. **Risk is minimized**: Each change is small and tested
2. **Quality is maintained**: Comprehensive testing and review
3. **Users are protected**: No breaking changes, gradual adoption
4. **Innovation is enabled**: Powerful new capabilities

The plan balances ambition with pragmatism, ensuring that Thoth gains cutting-edge agent capabilities while maintaining its reliability and ease of use.
