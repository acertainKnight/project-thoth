"""
State management for the research assistant agent.

This module defines the state structure used by LangGraph to manage
conversation flow and agent state.
"""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ResearchAgentState(BaseModel):
    """
    State definition for the research assistant agent.

    This state is used by LangGraph to track conversation history,
    current context, and any intermediate results.
    """

    # Conversation messages with special annotation for LangGraph
    messages: Annotated[list[BaseMessage], add_messages] = Field(
        default_factory=list, description='Conversation history as LangChain messages'
    )

    # Current context and metadata
    current_task: str | None = Field(
        default=None, description='Description of the current task being performed'
    )

    # Tool execution results
    last_tool_result: str | None = Field(
        default=None, description='Result from the last tool execution'
    )

    # User preferences and context
    user_context: dict[str, Any] = Field(
        default_factory=dict, description='User-specific context and preferences'
    )

    # Research context
    active_queries: list[str] = Field(
        default_factory=list, description='List of active research queries'
    )

    active_sources: list[str] = Field(
        default_factory=list, description='List of active discovery sources'
    )

    # Memory and session info
    session_id: str | None = Field(
        default=None, description='Session identifier for memory persistence'
    )

    # Error handling
    error: str | None = Field(
        default=None, description='Error message if something went wrong'
    )

    # Intermediate processing state
    intermediate_steps: list[dict[str, Any]] = Field(
        default_factory=list, description='Steps taken during processing'
    )

    # Allow dynamic model override for a single turn
    model_override: str | None = Field(
        default=None, description='Model to use for the current turn, if any'
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
