"""
Obsidian integration for Thoth.

This module provides FastAPI endpoints for integration with Obsidian.
The main endpoint allows downloading PDFs from URLs via Obsidian's URI capability.
"""

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from thoth.ingestion.pdf_downloader import download_pdf
from thoth.services.llm_router import LLMRouter
from thoth.utilities.config import get_config
from thoth.monitoring import HealthMonitor

app = FastAPI(
    title="Thoth Obsidian Integration",
    description="API for integrating Thoth with Obsidian",
    version="0.1.0",
)

# Add CORS middleware to allow requests from Obsidian
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin (including Obsidian)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

# Module-level variables to store configuration
# These will be set by the start_server function
pdf_dir: Path = None
notes_dir: Path = None
base_url: str = None
current_config: dict[str, Any] = {}

# Service manager initialized when the server starts
service_manager = None

# Global agent instance - will be initialized when server starts
research_agent = None
agent_adapter = None
llm_router = None


class ConnectionManager:
    """Manage active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str | dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                if isinstance(message, dict):
                    await connection.send_json(message)
                else:
                    await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


chat_ws_manager = ConnectionManager()
status_ws_manager = ConnectionManager()
progress_ws_manager = ConnectionManager()


async def notify_progress(message: str | dict[str, Any]) -> None:
    """Broadcast a progress update to all connected clients."""
    await progress_ws_manager.broadcast(message)


# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    timestamp: int | None = None
    id: str | None = None


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict[str, Any]] = []
    error: str | None = None
    id: str | None = None


class ResearchRequest(BaseModel):
    query: str
    type: str = "quick_research"
    max_results: int = 5
    include_citations: bool = True


class ResearchResponse(BaseModel):
    results: str = None
    response: str = None
    error: str = None


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration."""

    api_keys: dict[str, str] = {}
    settings: dict[str, Any] = {}
    directories: dict[str, str] = {}


class AgentRestartRequest(BaseModel):
    """Request model for restarting the agent."""

    update_config: bool = True
    new_config: ConfigUpdateRequest = None


@app.get("/health")
def health_check():
    """Health check endpoint returning service statuses."""
    global service_manager
    if service_manager is None:
        return JSONResponse({'status': 'uninitialized'})

    monitor = HealthMonitor(service_manager)
    return JSONResponse(monitor.overall_status())


@app.get("/download-pdf")
def download_pdf_endpoint(url: str = Query(..., description="PDF URL to download")):
    """
    Download a PDF from a URL and save it to the configured PDF directory.

    Args:
        url: The URL of the PDF to download.

    Returns:
        JSON response with download status and file path.
    """
    if pdf_dir is None:
        raise HTTPException(status_code=500, detail="PDF directory not configured")

    try:
        file_path = download_pdf(url, pdf_dir)
        return JSONResponse(
            {
                "status": "success",
                "message": f"PDF downloaded successfully to {file_path}",
                "file_path": str(file_path),
            }
        )
    except Exception as e:
        logger.error(f"Failed to download PDF from {url}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to download PDF: {e!s}"
        ) from e


@app.get("/view-markdown")
def view_markdown(path: str = Query(..., description="Path to markdown file")):
    """
    View the contents of a markdown file.

    Args:
        path: Path to the markdown file relative to the notes directory.

    Returns:
        JSON response with file contents.
    """
    if notes_dir is None:
        raise HTTPException(status_code=500, detail="Notes directory not configured")

    try:
        file_path = notes_dir / path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        return JSONResponse(
            {"status": "success", "content": content, "file_path": str(file_path)}
        )
    except Exception as e:
        logger.error(f"Failed to read markdown file {path}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to read file: {e!s}"
        ) from e


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat."""
    await chat_ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            conv_id = data.get("conversation_id")
            timestamp = data.get("timestamp")
            msg_id = data.get("id")

            if research_agent is None:
                await websocket.send_json({"error": "Research agent not initialized"})
                continue

            config = get_config()
            router = LLMRouter(config)
            model = router.select_model(message)
            session_id = conv_id or f"obsidian-{timestamp or 0}"

            response = research_agent.chat(
                message=message,
                session_id=session_id,
                model_override=model,
            )
            await websocket.send_json(
                {
                    "id": msg_id,
                    "response": response.get("response", "No response generated"),
                    "tool_calls": response.get("tool_calls", []),
                }
            )
    except WebSocketDisconnect:
        chat_ws_manager.disconnect(websocket)


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket) -> None:
    """WebSocket endpoint for status updates."""
    await status_ws_manager.connect(websocket)
    try:
        while True:
            status = "running" if research_agent else "not_initialized"
            await websocket.send_json({"status": status})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        status_ws_manager.disconnect(websocket)


@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket) -> None:
    """WebSocket endpoint for progress notifications."""
    await progress_ws_manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        progress_ws_manager.disconnect(websocket)


@app.post("/research/chat")
async def research_chat(request: ChatRequest) -> ChatResponse:
    """
    Chat endpoint for the research assistant.

    Args:
        request: Chat request containing message and conversation context.

    Returns:
        ChatResponse with the agent's reply.
    """
    if research_agent is None:
        raise HTTPException(status_code=503, detail="Research agent not initialized")

    try:
        # Initialize router and select model based on query
        config = get_config()
        llm_router = LLMRouter(config)
        selected_model = llm_router.select_model(request.message)

        # Generate session ID if not provided
        session_id = request.conversation_id or f"obsidian-{request.timestamp or 0}"

        # Get response from the agent
        response = research_agent.chat(
            message=request.message,
            session_id=session_id,
            model_override=selected_model,
        )

        return ChatResponse(
            response=response.get("response", "No response generated"),
            tool_calls=response.get("tool_calls", []),
            id=request.id,
        )

    except Exception as e:
        logger.error(f"Error in research chat: {e}")
        return ChatResponse(
            response="I encountered an error processing your request.", error=str(e)
        )


@app.post("/research/query")
async def research_query(request: ResearchRequest) -> ResearchResponse:
    """
    Direct research query endpoint for quick research tasks.

    Args:
        request: Research request with query and parameters.

    Returns:
        ResearchResponse with research results.
    """
    if research_agent is None:
        raise HTTPException(status_code=503, detail="Research agent not initialized")

    try:
        # Format the research request as a message
        research_message = f"""
        Please research: {request.query}

        Requirements:
        - Type: {request.type}
        - Max results: {request.max_results}
        - Include citations: {request.include_citations}

        Please provide a comprehensive research summary with key findings.
        """

        # Get response from the agent
        response = research_agent.chat(
            message=research_message,
            session_id=f"research-{request.query[:20]}-{hash(request.query)}",
        )

        return ResearchResponse(
            results=response.get("response", "No research results found"),
            response=response.get("response", "No research results found"),
        )

    except Exception as e:
        logger.error(f"Error in research query: {e}")
        return ResearchResponse(error=str(e))


@app.get("/agent/status")
def agent_status():
    """Agent status endpoint for Obsidian plugin health checks."""
    if research_agent is None:
        return JSONResponse(
            {
                "status": "not_initialized",
                "agent_initialized": False,
                "message": "Research agent not initialized",
            },
            status_code=503,
        )

    try:
        # Check if agent has tools available (basic functionality test)
        tools = research_agent.get_available_tools()
        return JSONResponse(
            {
                "status": "running",
                "agent_initialized": True,
                "tools_count": len(tools),
                "message": "Research agent is running and ready",
            }
        )
    except Exception as e:
        logger.error(f"Error checking agent status: {e}")
        return JSONResponse(
            {
                "status": "error",
                "agent_initialized": False,
                "error": str(e),
                "message": "Research agent encountered an error",
            },
            status_code=500,
        )


@app.get("/agent/tools")
def list_agent_tools():
    """List all available tools for the research agent."""
    if research_agent is None:
        raise HTTPException(status_code=503, detail="Research agent not initialized")

    try:
        tools = research_agent.get_available_tools()
        return JSONResponse({"tools": tools, "count": len(tools)})
    except Exception as e:
        logger.error(f"Error listing agent tools: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list tools: {e!s}"
        ) from e


@app.get("/agent/config")
def get_agent_config():
    """Get current agent configuration."""
    global current_config

    try:
        # Get current config from the global config or reload it
        config = get_config()

        # Return sanitized config (without sensitive data)
        sanitized_config = {
            "directories": {
                "workspace_dir": str(config.workspace_dir),
                "pdf_dir": str(config.pdf_dir),
                "notes_dir": str(config.notes_dir),
                "queries_dir": str(config.queries_dir),
                "agent_storage_dir": str(config.agent_storage_dir),
            },
            "api_server": {
                "host": config.api_server_config.host,
                "port": config.api_server_config.port,
                "base_url": config.api_server_config.base_url,
            },
            "llm_models": {
                "llm_model": config.llm_config.model,
                "research_agent_model": config.research_agent_llm_config.model,
            },
            "discovery": {
                "auto_start_scheduler": config.discovery_config.auto_start_scheduler,
                "default_max_articles": config.discovery_config.default_max_articles,
            },
            "has_api_keys": {
                "mistral": bool(config.api_keys.mistral_key),
                "openrouter": bool(config.api_keys.openrouter_key),
            },
        }

        return JSONResponse(sanitized_config)

    except Exception as e:
        logger.error(f"Error getting agent config: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get config: {e!s}"
        ) from e


@app.post("/agent/config")
async def update_agent_config(request: ConfigUpdateRequest):
    """Update agent configuration dynamically."""
    try:
        # Update environment variables
        env_updates = {}

        # Handle API keys
        if request.api_keys:
            for key, value in request.api_keys.items():
                if value:  # Only update non-empty values
                    env_key = f"API_{key.upper()}_KEY"
                    env_updates[env_key] = value
                    os.environ[env_key] = value

        # Handle directory settings
        if request.directories:
            for key, value in request.directories.items():
                if value:  # Only update non-empty values
                    env_key = key.upper() + "_DIR"
                    env_updates[env_key] = value
                    os.environ[env_key] = value

        # Handle other settings
        if request.settings:
            for key, value in request.settings.items():
                if value is not None:  # Allow False values
                    env_updates[key.upper()] = str(value)
                    os.environ[key.upper()] = str(value)

        logger.info(f"Updated environment variables: {list(env_updates.keys())}")

        return JSONResponse(
            {
                "status": "success",
                "message": "Configuration updated successfully",
                "updated_keys": list(env_updates.keys()),
                "note": "Agent restart required for changes to take full effect",
            }
        )

    except Exception as e:
        logger.error(f"Error updating agent config: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {e!s}"
        ) from e


@app.post("/agent/restart")
async def restart_agent(request: AgentRestartRequest = None):
    """Restart the agent process."""
    try:
        # Update config if requested
        if request and request.update_config and request.new_config:
            await update_agent_config(request.new_config)

        # Get current process info
        current_pid = os.getpid()

        # For development/local mode, try to restart gracefully
        if hasattr(sys, "_called_from_test"):
            # In test mode, just reinitialize
            await reinitialize_agent()
            return JSONResponse(
                {
                    "status": "success",
                    "message": "Agent reinitialized successfully (test mode)",
                    "method": "reinitialize",
                }
            )

        # Try to restart the process
        try:
            # Get the command line arguments
            python_executable = sys.executable
            script_args = sys.argv

            logger.info(f"Restarting agent process (PID: {current_pid})")
            logger.info(f'Command: {python_executable} {" ".join(script_args)}')

            # Start new process
            subprocess.Popen([python_executable, *script_args])

            # Send response before terminating
            response_data = {
                "status": "success",
                "message": "Agent restart initiated",
                "old_pid": current_pid,
                "method": "process_restart",
            }

            # Schedule process termination after response
            import asyncio

            asyncio.create_task(delayed_shutdown())  # noqa: RUF006

            return JSONResponse(response_data)

        except Exception as restart_error:
            logger.error(f"Process restart failed: {restart_error}")

            # Fallback to agent reinitialization
            await reinitialize_agent()
            return JSONResponse(
                {
                    "status": "success",
                    "message": "Agent reinitialized successfully (fallback)",
                    "method": "reinitialize",
                    "restart_error": str(restart_error),
                }
            )

    except Exception as e:
        logger.error(f"Error restarting agent: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to restart agent: {e!s}"
        ) from e


async def delayed_shutdown():
    """Shutdown the process after a short delay."""
    import asyncio

    await asyncio.sleep(1)  # Give time for response to be sent
    logger.info("Terminating process for restart...")
    os.kill(os.getpid(), signal.SIGTERM)


async def reinitialize_agent():
    """Reinitialize the agent without restarting the process."""
    global research_agent, agent_adapter, llm_router, service_manager

    try:
        logger.info("Reinitializing research agent...")

        from thoth.ingestion.agent_v2 import create_research_assistant
        from thoth.pipeline import ThothPipeline

        # Create new pipeline with updated config
        pipeline = ThothPipeline()
        service_manager = pipeline.services

        # Create new research agent
        research_agent = create_research_assistant(
            service_manager=service_manager,
            enable_memory=True,
        )

        # Initialize router
        config = get_config()
        llm_router = LLMRouter(config)

        logger.info(
            f"Research agent reinitialized with {len(research_agent.get_available_tools())} tools"
        )

    except Exception as e:
        logger.error(f"Failed to reinitialize research agent: {e}")
        raise


@app.post("/agent/sync-settings")
async def sync_obsidian_settings(settings: dict[str, Any]):
    """Sync settings from Obsidian plugin to backend."""
    try:
        # Map Obsidian settings to environment variables
        env_updates = {}

        # API Keys
        if settings.get("mistralKey"):
            env_updates["API_MISTRAL_KEY"] = settings["mistralKey"]
            os.environ["API_MISTRAL_KEY"] = settings["mistralKey"]

        if settings.get("openrouterKey"):
            env_updates["API_OPENROUTER_KEY"] = settings["openrouterKey"]
            os.environ["API_OPENROUTER_KEY"] = settings["openrouterKey"]

        # Directories
        if settings.get("workspaceDirectory"):
            env_updates["WORKSPACE_DIR"] = settings["workspaceDirectory"]
            os.environ["WORKSPACE_DIR"] = settings["workspaceDirectory"]

        if settings.get("obsidianDirectory"):
            env_updates["NOTES_DIR"] = settings["obsidianDirectory"]
            os.environ["NOTES_DIR"] = settings["obsidianDirectory"]

        # Server settings
        if settings.get("endpointHost"):
            env_updates["ENDPOINT_HOST"] = settings["endpointHost"]
            os.environ["ENDPOINT_HOST"] = settings["endpointHost"]

        if settings.get("endpointPort"):
            env_updates["ENDPOINT_PORT"] = str(settings["endpointPort"])
            os.environ["ENDPOINT_PORT"] = str(settings["endpointPort"])

        logger.info(f"Synced settings from Obsidian: {list(env_updates.keys())}")

        return JSONResponse(
            {
                "status": "success",
                "message": "Settings synced successfully",
                "synced_keys": list(env_updates.keys()),
            }
        )

    except Exception as e:
        logger.error(f"Error syncing Obsidian settings: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to sync settings: {e!s}"
        ) from e


def start_server(
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

    Args:
        host (str): Host to bind the server to.
        port (int): Port to bind the server to.
        pdf_directory (Path): Directory where PDFs will be stored.
        notes_directory (Path): Directory where notes are stored (Obsidian vault).
        api_base_url (str): Base URL for the API.
        pipeline (ThothPipeline | None): Optional ThothPipeline instance.
        reload (bool): Whether to enable auto-reload for development.
    """
    global pdf_dir, notes_dir, base_url, research_agent, agent_adapter, llm_router, service_manager

    # Set module-level configuration
    pdf_dir = pdf_directory
    notes_dir = notes_directory
    base_url = api_base_url

    logger.info(f"Starting Obsidian API server on {host}:{port}")
    logger.info(f"PDF directory: {pdf_dir}")
    logger.info(f"Notes directory: {notes_dir}")
    logger.info(f"API base URL: {base_url}")

    # Initialize the research agent
    try:
        logger.info("Initializing research agent...")
        from thoth.ingestion.agent_v2 import create_research_assistant

        # Use provided pipeline or create a new one
        if pipeline is None:
            from thoth.pipeline import ThothPipeline

            pipeline = ThothPipeline()

        service_manager = pipeline.services

        # Create the research agent
        research_agent = create_research_assistant(
            service_manager=service_manager,
            enable_memory=True,
        )

        # Initialize router
        config = get_config()
        llm_router = LLMRouter(config)

        logger.info(
            f"Research agent initialized with {len(research_agent.get_available_tools())} tools"
        )

    except Exception as e:
        logger.error(f"Failed to initialize research agent: {e}")
        logger.warning("Server will start without research agent functionality")

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    # This is for development purposes only
    from pathlib import Path

    start_server(
        "127.0.0.1",
        8000,
        Path("./data/pdf"),
        Path("./data/notes"),
        "http://127.0.0.1:8000",
    )
