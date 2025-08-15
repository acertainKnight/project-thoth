"""
API routers for Thoth server.

This module organizes API endpoints into logical groups for better maintainability.
"""

from .agent import router as agent_router
from .chat import router as chat_router
from .config import router as config_router
from .health import router as health_router
from .operations import router as operations_router
from .research import router as research_router
from .tools import router as tools_router
from .websocket import router as websocket_router

# Export all routers
routers = [
    agent_router,
    chat_router,
    config_router,
    health_router,
    operations_router,
    research_router,
    tools_router,
    websocket_router,
]

__all__ = [
    'routers',
    'agent_router',
    'chat_router', 
    'config_router',
    'health_router',
    'operations_router',
    'research_router',
    'tools_router',
    'websocket_router',
]