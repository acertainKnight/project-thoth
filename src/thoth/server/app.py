"""
Thoth API Server - Modular Application.

This is the new modular structure for the Thoth API server, organizing
endpoints into logical routers for better maintainability.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from thoth.server.routers import (
    health_router,
    websocket_router,
    chat_router,
)
from thoth.utilities.config import get_config

# Initialize configuration
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting Thoth API server...")
    
    # Initialize services
    from thoth.services.service_manager import ServiceManager
    app.state.service_manager = ServiceManager(config)
    app.state.service_manager.initialize()
    
    # Initialize chat manager
    from thoth.server.chat_models import ChatManager
    app.state.chat_manager = ChatManager(
        db_path=config.data_dir / 'chat' / 'messages.db'
    )
    
    # Initialize research agent
    try:
        from thoth.ingestion.agent_v2.core.agent import create_research_assistant_async
        app.state.research_agent = await create_research_assistant_async(
            service_manager=app.state.service_manager,
            enable_memory=True,
        )
        logger.info("Research agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize research agent: {e}")
        app.state.research_agent = None
    
    yield
    
    # Cleanup
    logger.info("Shutting down Thoth API server...")
    if hasattr(app.state, 'research_agent') and app.state.research_agent:
        # Cleanup agent resources
        pass


# Create FastAPI app
app = FastAPI(
    title="Thoth Research Assistant API",
    description="AI-powered research assistant for academic literature management",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.endpoint_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
from thoth.server.routers import routers

for router in routers:
    app.include_router(router)


# Dependency injection helpers
def get_service_manager():
    """Get service manager from app state."""
    return app.state.service_manager


def get_chat_manager():
    """Get chat manager from app state."""
    return app.state.chat_manager


def get_research_agent():
    """Get research agent from app state."""
    return app.state.research_agent


def get_pdf_dir():
    """Get PDF directory from config."""
    return config.pdf_dir


def get_notes_dir():
    """Get notes directory from config."""
    return config.notes_dir


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.endpoint_config.host,
        port=config.endpoint_config.port,
        reload=True,
    )