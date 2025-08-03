"""
Modern research assistant agent using LangGraph and MCP framework.

This package provides a clean, modular implementation of the research assistant
with tool-based architecture for managing research activities.
"""

from thoth.ingestion.agent_v2.core.agent import (
    ResearchAssistant,
    create_research_assistant,
    create_research_assistant_async,
)
from thoth.ingestion.agent_v2.core.state import ResearchAgentState
from thoth.ingestion.agent_v2.server import start_mcp_server

__all__ = [
    'ResearchAgentState',
    'ResearchAssistant',
    'create_research_assistant',
    'create_research_assistant_async',
    'start_mcp_server',
]
