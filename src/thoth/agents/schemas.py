"""
Agent configuration schemas for Thoth's Letta-based agent system.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a Letta subagent."""

    name: str = Field(..., description='Unique agent name (lowercase, hyphens)')
    description: str = Field(..., description='What the agent does')
    type: str = Field(
        default='custom',
        description='Agent type: research, analysis, discovery, custom',
    )
    system_prompt: str = Field(..., description='System prompt defining agent behavior')
    tools: list[str] = Field(
        default_factory=list, description='Available tools for this agent'
    )
    memory_blocks: dict[str, int] = Field(
        default_factory=lambda: {'identity': 2000, 'context': 3000, 'findings': 5000},
        description='Memory blocks with their limits',
    )
    capabilities: list[str] = Field(
        default_factory=list, description='Agent capabilities'
    )
    created_by: str = Field(..., description='User who created this agent')
    created_at: datetime = Field(default_factory=datetime.now)
    version: str = Field(default='1.0', description='Agent version')
    is_system: bool = Field(default=False, description='Whether this is a system agent')


class AgentInvocation(BaseModel):
    """Request to invoke a specific agent."""

    agent_name: str = Field(..., description='Name of agent to invoke')
    message: str = Field(..., description='Message to send to agent')
    context: dict[str, Any] | None = Field(None, description='Additional context')
    user_id: str = Field(..., description='User making the request')
    thread_id: str | None = Field(None, description='Conversation thread ID')


class AgentResponse(BaseModel):
    """Response from an agent invocation."""

    agent_name: str
    response: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    tools_used: list[str] = Field(default_factory=list)
    memory_updated: bool = Field(default=False)


class AgentCreationRequest(BaseModel):
    """Request to create a new agent from chat."""

    description: str = Field(
        ..., description='Natural language description of desired agent'
    )
    user_id: str = Field(..., description='User requesting agent creation')
    agent_type: str | None = Field(None, description='Suggested agent type')
    tools: list[str] | None = Field(None, description='Specific tools to assign')


class AgentListResponse(BaseModel):
    """Response containing list of available agents."""

    system_agents: list[AgentConfig] = Field(default_factory=list)
    user_agents: list[AgentConfig] = Field(default_factory=list)
    total_count: int = 0
