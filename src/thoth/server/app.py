"""
Thoth API Server - Modular Application.

This is the new modular structure for the Thoth API server, organizing
endpoints into logical routers for better maintainability.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:8080", "*"],  # TODO: Make this configurable
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


def create_app():
    """Create a new FastAPI app instance. Used for testing."""
    return app


def get_research_agent():
    """Get research agent from app state."""
    return app.state.research_agent


def get_pdf_dir():
    """Get PDF directory from config."""
    return config.pdf_dir


def get_notes_dir():
    """Get notes directory from config."""
    return config.notes_dir


# Legacy compatibility functions
async def start_server(
    host: str,
    port: int,
    pdf_directory: Path,
    notes_directory: Path,
    api_base_url: str,
    pipeline: Any | None = None,
    reload: bool = False,
):
    """
    Start the FastAPI server with research agent integration.
    
    This is a compatibility function for the legacy API.
    """
    import uvicorn
    
    # Override config if needed
    if pdf_directory:
        config.pdf_dir = pdf_directory
    if notes_directory:
        config.notes_dir = notes_directory
    
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
    )


def start_obsidian_server(
    host: str,
    port: int,
    pdf_directory: Path,
    notes_directory: Path,
    api_base_url: str,
    pipeline: Any | None = None,
    reload: bool = False,
):
    """
    Synchronous wrapper for starting the server.
    
    This function provides backward compatibility with the old API.
    """
    import asyncio
    
    asyncio.run(
        start_server(
            host=host,
            port=port,
            pdf_directory=pdf_directory,
            notes_directory=notes_directory,
            api_base_url=api_base_url,
            pipeline=pipeline,
            reload=reload,
        )
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.endpoint_config.host,
        port=config.endpoint_config.port,
        reload=True,
    )