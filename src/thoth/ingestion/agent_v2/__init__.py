"""
Modern research assistant agent using LangGraph and MCP framework.

This package provides a clean, modular implementation of the research assistant
with tool-based architecture for managing research activities.
"""

from thoth.ingestion.agent_v2.core.agent import (
    ResearchAssistant,
    create_research_assistant,
)
from thoth.ingestion.agent_v2.core.state import ResearchAgentState

__all__ = [
    'ResearchAgentState',
    'ResearchAssistant',
    'create_research_assistant',
]
