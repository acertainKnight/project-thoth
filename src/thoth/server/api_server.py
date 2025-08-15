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
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from thoth.ingestion.pdf_downloader import download_pdf
from thoth.monitoring import HealthMonitor
from thoth.server.chat_models import ChatMessage, ChatPersistenceManager
from thoth.services.llm_router import LLMRouter
from thoth.utilities.config import get_config


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle FastAPI application lifespan events."""
    # Startup
    logger.info('Starting Thoth server application...')
    try:
        yield
    except asyncio.CancelledError:
        # Handle graceful cancellation during shutdown
        logger.info('Application lifespan cancelled, proceeding with shutdown...')
    finally:
        # Shutdown
        logger.info('Shutting down Thoth server application...')
        try:
            await shutdown_background_tasks(timeout=5.0)
            await shutdown_mcp_server(timeout=5.0)
        except asyncio.CancelledError:
            logger.info('Shutdown tasks cancelled, forcing cleanup...')
        except Exception as e:
            logger.error(f'Error during application shutdown: {e}')


app = FastAPI(
    title='Thoth Obsidian Integration',
    description='API for integrating Thoth with Obsidian',
    version='0.1.0',
    lifespan=lifespan,
)

# Add CORS middleware to allow requests from Obsidian
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],  # Allow requests from any origin (including Obsidian)
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
    allow_headers=['*'],
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

# Chat persistence manager - will be initialized when server starts
chat_manager: ChatPersistenceManager = None


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

# Progress tracking for long-running operations
operation_progress: dict[str, dict[str, Any]] = {}
operation_lock = threading.Lock()

# Track background tasks to prevent garbage collection
background_tasks: set[asyncio.Task[Any]] = set()


def create_background_task(coro) -> None:
    """Create a background task and track it to prevent garbage collection."""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def shutdown_background_tasks(timeout: float = 10.0) -> None:
    """Gracefully shutdown all background tasks."""
    if not background_tasks:
        logger.info('No background tasks to shutdown')
        return

    logger.info(f'Shutting down {len(background_tasks)} background tasks...')

    # Cancel all background tasks
    for task in background_tasks.copy():
        if not task.done():
            task.cancel()

    # Wait for tasks to complete with timeout, handling cancellation properly
    if background_tasks:
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*background_tasks, return_exceptions=True),
                timeout=timeout,
            )
            # Check results for any non-CancelledError exceptions
            for result in results:
                if isinstance(result, Exception) and not isinstance(
                    result, asyncio.CancelledError
                ):
                    logger.warning(f'Background task shutdown with exception: {result}')
            logger.info('All background tasks shutdown gracefully')
        except TimeoutError:
            logger.warning(f'Some background tasks did not shutdown within {timeout}s')
        except asyncio.CancelledError:
            logger.info('Background task shutdown was cancelled')
        except Exception as e:
            logger.error(f'Error shutting down background tasks: {e}')

    # Clear the set
    background_tasks.clear()


async def shutdown_mcp_server(timeout: float = 10.0) -> None:
    """Gracefully shutdown the MCP server background task."""
    if not hasattr(_start_mcp_server_background, '_background_tasks'):
        logger.info('No MCP server tasks to shutdown')
        return

    mcp_tasks = _start_mcp_server_background._background_tasks.copy()
    if not mcp_tasks:
        logger.info('No MCP server tasks running')
        return

    logger.info(f'Shutting down {len(mcp_tasks)} MCP server tasks...')

    # Cancel all MCP tasks gracefully
    for task in mcp_tasks:
        if not task.done():
            task.cancel()

    # Wait for tasks to complete with timeout, handling cancellation properly
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*mcp_tasks, return_exceptions=True), timeout=timeout
        )
        # Check results for any non-CancelledError exceptions
        for result in results:
            if isinstance(result, Exception) and not isinstance(
                result, asyncio.CancelledError
            ):
                logger.warning(f'MCP task shutdown with exception: {result}')
        logger.info('MCP server tasks shutdown gracefully')
    except TimeoutError:
        logger.warning(f'MCP server tasks did not shutdown within {timeout}s')
    except asyncio.CancelledError:
        logger.info('MCP server shutdown was cancelled')
    except Exception as e:
        logger.error(f'Error shutting down MCP server tasks: {e}')

    # Clear the set
    _start_mcp_server_background._background_tasks.clear()


async def notify_progress(message: str | dict[str, Any]) -> None:
    """Broadcast a progress update to all connected clients."""
    await progress_ws_manager.broadcast(message)


def update_operation_progress(
    operation_id: str,
    status: str,
    progress: float = 0.0,
    message: str = '',
    result: Any = None,
) -> None:
    """Update progress for a long-running operation."""
    with operation_lock:
        operation_progress[operation_id] = {
            'status': status,  # 'running', 'completed', 'failed'
            'progress': progress,  # 0.0 to 100.0
            'message': message,
            'result': result,
            'timestamp': time.time(),
        }

    # Broadcast to WebSocket clients
    create_background_task(
        notify_progress(
            {
                'operation_id': operation_id,
                'status': status,
                'progress': progress,
                'message': message,
            }
        )
    )


def get_operation_status(operation_id: str) -> dict[str, Any] | None:
    """Get the current status of an operation."""
    with operation_lock:
        return operation_progress.get(operation_id)


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


class CreateSessionRequest(BaseModel):
    title: str = 'New Chat'
    metadata: dict[str, Any] = {}


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    metadata: dict[str, Any] | None = None


class SessionListResponse(BaseModel):
    sessions: list[dict[str, Any]]
    total_count: int


class MessageHistoryResponse(BaseModel):
    messages: list[dict[str, Any]]
    session_info: dict[str, Any]
    total_count: int
    has_more: bool


class ResearchRequest(BaseModel):
    query: str
    type: str = 'quick_research'
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


class StreamingOperationRequest(BaseModel):
    """Request model for streaming operations."""

    operation_type: str  # 'pdf_process', 'discovery_run', 'batch_process'
    parameters: dict[str, Any] = {}
    operation_id: str | None = None


class BatchProcessRequest(BaseModel):
    """Request model for batch processing operations."""

    items: list[dict[str, Any]]  # List of items to process
    operation_type: str  # Type of operation to perform on each item
    max_concurrent: int = 3  # Maximum concurrent operations


class CommandExecutionRequest(BaseModel):
    """Request model for CLI command execution."""

    command: str  # CLI command to execute (e.g., 'discovery', 'pdf-locate')
    args: list[str] = []  # Command arguments
    options: dict[str, Any] = {}  # Command options
    stream_output: bool = True  # Whether to stream output


class ToolExecutionRequest(BaseModel):
    """Request model for direct tool execution."""

    tool_name: str  # Name of the tool to execute
    parameters: dict[str, Any] = {}  # Tool parameters
    bypass_agent: bool = True  # Whether to bypass the agent


@app.get('/health')
def health_check():
    """Health check endpoint returning service statuses."""
    global service_manager
    if service_manager is None:
        return JSONResponse({'status': 'uninitialized'})

    monitor = HealthMonitor(service_manager)
    return JSONResponse(monitor.overall_status())


@app.get('/download-pdf')
def download_pdf_endpoint(url: str = Query(..., description='PDF URL to download')):
    """
    Download a PDF from a URL and save it to the configured PDF directory.

    Args:
        url: The URL of the PDF to download.

    Returns:
        JSON response with download status and file path.
    """
    if pdf_dir is None:
        raise HTTPException(status_code=500, detail='PDF directory not configured')

    try:
        file_path = download_pdf(url, pdf_dir)
        return JSONResponse(
            {
                'status': 'success',
                'message': f'PDF downloaded successfully to {file_path}',
                'file_path': str(file_path),
            }
        )
    except Exception as e:
        logger.error(f'Failed to download PDF from {url}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to download PDF: {e!s}'
        ) from e


@app.get('/view-markdown')
def view_markdown(path: str = Query(..., description='Path to markdown file')):
    """
    View the contents of a markdown file.

    Args:
        path: Path to the markdown file relative to the notes directory.

    Returns:
        JSON response with file contents.
    """
    if notes_dir is None:
        raise HTTPException(status_code=500, detail='Notes directory not configured')

    try:
        file_path = notes_dir / path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail='File not found')

        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        return JSONResponse(
            {'status': 'success', 'content': content, 'file_path': str(file_path)}
        )
    except Exception as e:
        logger.error(f'Failed to read markdown file {path}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to read file: {e!s}'
        ) from e


@app.websocket('/ws/chat')
async def websocket_chat(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time chat with persistence."""
    await chat_ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get('message', '')
            conv_id = data.get('conversation_id')
            timestamp = data.get('timestamp')
            msg_id = data.get('id')

            if research_agent is None:
                await websocket.send_json({'error': 'Research agent not initialized'})
                continue

            config = get_config()
            router = LLMRouter(config)
            model = router.select_model(message)
            session_id = (
                conv_id or f'obsidian-ws-{timestamp or int(datetime.now().timestamp())}'
            )

            # Store user message if chat manager is available
            user_message_id = None
            if chat_manager is not None:
                try:
                    # Ensure session exists
                    existing_session = chat_manager.get_session(session_id)
                    if not existing_session:
                        # Auto-generate title from first message
                        title = message[:50] + '...' if len(message) > 50 else message
                        chat_manager.create_session(
                            title=title, metadata={'source': 'obsidian-websocket'}
                        )

                    # Store user message
                    user_message = ChatMessage(
                        session_id=session_id,
                        role='user',
                        content=message,
                        metadata={'source': 'obsidian-websocket', 'message_id': msg_id},
                    )
                    chat_manager.add_message(user_message)
                    user_message_id = user_message.id
                except Exception as e:
                    logger.warning(f'Failed to store WebSocket user message: {e}')

            response = await research_agent.chat(
                message=message,
                session_id=session_id,
                model_override=model,
            )

            agent_response = response.get('response', 'No response generated')
            tool_calls = response.get('tool_calls', [])

            # Store assistant response if chat manager is available
            if chat_manager is not None:
                try:
                    assistant_message = ChatMessage(
                        session_id=session_id,
                        role='assistant',
                        content=agent_response,
                        tool_calls=tool_calls,
                        metadata={'model': model, 'source': 'obsidian-websocket'},
                        parent_message_id=user_message_id,
                    )
                    chat_manager.add_message(assistant_message)
                except Exception as e:
                    logger.warning(f'Failed to store WebSocket assistant message: {e}')

            await websocket.send_json(
                {
                    'id': msg_id,
                    'session_id': session_id,
                    'response': agent_response,
                    'tool_calls': tool_calls,
                }
            )
    except WebSocketDisconnect:
        chat_ws_manager.disconnect(websocket)


@app.websocket('/ws/status')
async def websocket_status(websocket: WebSocket) -> None:
    """WebSocket endpoint for status updates."""
    await status_ws_manager.connect(websocket)
    try:
        while True:
            status = 'running' if research_agent else 'not_initialized'
            await websocket.send_json({'status': status})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        status_ws_manager.disconnect(websocket)


@app.websocket('/ws/progress')
async def websocket_progress(websocket: WebSocket) -> None:
    """WebSocket endpoint for progress notifications."""
    await progress_ws_manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        progress_ws_manager.disconnect(websocket)


# ============================================================================
# CHAT SESSION MANAGEMENT ENDPOINTS
# ============================================================================


@app.post('/chat/sessions')
async def create_chat_session(request: CreateSessionRequest) -> dict[str, Any]:
    """Create a new chat session."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        session = chat_manager.create_session(
            title=request.title, metadata=request.metadata
        )

        return {
            'status': 'success',
            'session': {
                'id': session.id,
                'title': session.title,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'is_active': session.is_active,
                'metadata': session.metadata,
                'message_count': session.message_count,
                'last_message_preview': session.last_message_preview,
            },
        }
    except Exception as e:
        logger.error(f'Error creating chat session: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to create session: {e!s}'
        ) from e


@app.get('/chat/sessions')
async def list_chat_sessions(
    active_only: bool = True, limit: int = 50
) -> SessionListResponse:
    """List chat sessions."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        sessions = chat_manager.list_sessions(active_only=active_only, limit=limit)

        session_data = []
        for session in sessions:
            session_data.append(
                {
                    'id': session.id,
                    'title': session.title,
                    'created_at': session.created_at.isoformat(),
                    'updated_at': session.updated_at.isoformat(),
                    'is_active': session.is_active,
                    'metadata': session.metadata,
                    'message_count': session.message_count,
                    'last_message_preview': session.last_message_preview,
                }
            )

        return SessionListResponse(sessions=session_data, total_count=len(session_data))
    except Exception as e:
        logger.error(f'Error listing chat sessions: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list sessions: {e!s}'
        ) from e


@app.get('/chat/sessions/{session_id}')
async def get_chat_session(session_id: str) -> dict[str, Any]:
    """Get a specific chat session."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        session = chat_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')

        return {
            'status': 'success',
            'session': {
                'id': session.id,
                'title': session.title,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'is_active': session.is_active,
                'metadata': session.metadata,
                'message_count': session.message_count,
                'last_message_preview': session.last_message_preview,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting chat session: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get session: {e!s}'
        ) from e


@app.put('/chat/sessions/{session_id}')
async def update_chat_session(
    session_id: str, request: UpdateSessionRequest
) -> dict[str, Any]:
    """Update a chat session."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        success = chat_manager.update_session(
            session_id=session_id, title=request.title, metadata=request.metadata
        )

        if not success:
            raise HTTPException(status_code=404, detail='Session not found')

        # Get updated session
        session = chat_manager.get_session(session_id)

        return {
            'status': 'success',
            'message': 'Session updated successfully',
            'session': {
                'id': session.id,
                'title': session.title,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'is_active': session.is_active,
                'metadata': session.metadata,
                'message_count': session.message_count,
                'last_message_preview': session.last_message_preview,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating chat session: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to update session: {e!s}'
        ) from e


@app.delete('/chat/sessions/{session_id}')
async def delete_chat_session(session_id: str) -> dict[str, Any]:
    """Delete a chat session and all its messages."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        success = chat_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail='Session not found')

        return {'status': 'success', 'message': 'Session deleted successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting chat session: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to delete session: {e!s}'
        ) from e


@app.post('/chat/sessions/{session_id}/archive')
async def archive_chat_session(session_id: str) -> dict[str, Any]:
    """Archive a chat session (mark as inactive)."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        success = chat_manager.archive_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail='Session not found')

        return {'status': 'success', 'message': 'Session archived successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error archiving chat session: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to archive session: {e!s}'
        ) from e


@app.get('/chat/sessions/{session_id}/messages')
async def get_chat_history(
    session_id: str, limit: int = 100, offset: int = 0
) -> MessageHistoryResponse:
    """Get chat history for a session."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        # Get session info
        session = chat_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')

        # Get messages
        messages = chat_manager.get_messages(session_id, limit=limit, offset=offset)
        total_count = chat_manager.get_message_count(session_id)

        message_data = []
        for msg in messages:
            message_data.append(
                {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'tool_calls': msg.tool_calls,
                    'metadata': msg.metadata,
                    'parent_message_id': msg.parent_message_id,
                }
            )

        return MessageHistoryResponse(
            messages=message_data,
            session_info={
                'id': session.id,
                'title': session.title,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'is_active': session.is_active,
                'metadata': session.metadata,
                'message_count': session.message_count,
            },
            total_count=total_count,
            has_more=(offset + len(messages)) < total_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting chat history: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get chat history: {e!s}'
        ) from e


@app.get('/chat/search')
async def search_chat_messages(
    query: str, session_id: str | None = None, limit: int = 50
) -> dict[str, Any]:
    """Search chat messages by content."""
    if chat_manager is None:
        raise HTTPException(status_code=503, detail='Chat manager not initialized')

    try:
        messages = chat_manager.search_messages(
            query, session_id=session_id, limit=limit
        )

        message_data = []
        for msg in messages:
            message_data.append(
                {
                    'id': msg.id,
                    'session_id': msg.session_id,
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'tool_calls': msg.tool_calls,
                    'metadata': msg.metadata,
                    'parent_message_id': msg.parent_message_id,
                }
            )

        return {
            'status': 'success',
            'query': query,
            'results': message_data,
            'result_count': len(message_data),
            'session_filter': session_id,
        }
    except Exception as e:
        logger.error(f'Error searching chat messages: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to search messages: {e!s}'
        ) from e


# ============================================================================
# ENHANCED CHAT ENDPOINTS
# ============================================================================


@app.post('/research/chat')
async def research_chat(request: ChatRequest) -> ChatResponse:
    """
    Enhanced chat endpoint with persistence support.

    Args:
        request: Chat request containing message and conversation context.

    Returns:
        ChatResponse with the agent's reply.
    """
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        # Initialize router and select model based on query
        config = get_config()
        llm_router = LLMRouter(config)
        selected_model = llm_router.select_model(request.message)

        # Generate session ID if not provided
        session_id = (
            request.conversation_id
            or f'obsidian-{request.timestamp or int(datetime.now().timestamp())}'
        )

        # Store user message if chat manager is available
        user_message_id = None
        if chat_manager is not None:
            try:
                # Ensure session exists
                existing_session = chat_manager.get_session(session_id)
                if not existing_session:
                    # Auto-generate title from first message
                    title = (
                        request.message[:50] + '...'
                        if len(request.message) > 50
                        else request.message
                    )
                    chat_manager.create_session(
                        title=title, metadata={'source': 'obsidian'}
                    )

                # Store user message
                user_message = ChatMessage(
                    session_id=session_id,
                    role='user',
                    content=request.message,
                    metadata={'source': 'obsidian', 'message_id': request.id},
                )
                chat_manager.add_message(user_message)
                user_message_id = user_message.id
            except Exception as e:
                logger.warning(f'Failed to store user message: {e}')

        # Get response from the agent
        response = await research_agent.chat(
            message=request.message,
            session_id=session_id,
            model_override=selected_model,
        )

        agent_response = response.get('response', 'No response generated')
        tool_calls = response.get('tool_calls', [])

        # Store assistant response if chat manager is available
        if chat_manager is not None:
            try:
                assistant_message = ChatMessage(
                    session_id=session_id,
                    role='assistant',
                    content=agent_response,
                    tool_calls=tool_calls,
                    metadata={'model': selected_model, 'source': 'obsidian'},
                    parent_message_id=user_message_id,
                )
                chat_manager.add_message(assistant_message)
            except Exception as e:
                logger.warning(f'Failed to store assistant message: {e}')

        return ChatResponse(
            response=agent_response,
            tool_calls=tool_calls,
            id=request.id,
        )

    except Exception as e:
        logger.error(f'Error in research chat: {e}')
        return ChatResponse(
            response='I encountered an error processing your request.', error=str(e)
        )


@app.post('/research/query')
async def research_query(request: ResearchRequest) -> ResearchResponse:
    """
    Direct research query endpoint for quick research tasks.

    Args:
        request: Research request with query and parameters.

    Returns:
        ResearchResponse with research results.
    """
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

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
        response = await research_agent.chat(
            message=research_message,
            session_id=f'research-{request.query[:20]}-{hash(request.query)}',
        )

        return ResearchResponse(
            results=response.get('response', 'No research results found'),
            response=response.get('response', 'No research results found'),
        )

    except Exception as e:
        logger.error(f'Error in research query: {e}')
        return ResearchResponse(error=str(e))


@app.get('/agent/status')
def agent_status():
    """Agent status endpoint for Obsidian plugin health checks."""
    if research_agent is None:
        return JSONResponse(
            {
                'status': 'not_initialized',
                'agent_initialized': False,
                'message': 'Research agent not initialized',
            },
            status_code=503,
        )

    try:
        # Check if agent has tools available (basic functionality test)
        tools = research_agent.get_available_tools()
        return JSONResponse(
            {
                'status': 'running',
                'agent_initialized': True,
                'tools_count': len(tools),
                'message': 'Research agent is running and ready',
            }
        )
    except Exception as e:
        logger.error(f'Error checking agent status: {e}')
        return JSONResponse(
            {
                'status': 'error',
                'agent_initialized': False,
                'error': str(e),
                'message': 'Research agent encountered an error',
            },
            status_code=500,
        )


@app.get('/agent/tools')
def list_agent_tools():
    """List all available tools for the research agent."""
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        tools = research_agent.get_available_tools()
        return JSONResponse({'tools': tools, 'count': len(tools)})
    except Exception as e:
        logger.error(f'Error listing agent tools: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list tools: {e!s}'
        ) from e


@app.get('/agent/config')
def get_agent_config():
    """Get current agent configuration."""
    global current_config

    try:
        # Get current config from the global config or reload it
        config = get_config()

        # Return sanitized config (without sensitive data)
        sanitized_config = {
            'directories': {
                'workspace_dir': str(config.workspace_dir),
                'pdf_dir': str(config.pdf_dir),
                'notes_dir': str(config.notes_dir),
                'queries_dir': str(config.queries_dir),
                'agent_storage_dir': str(config.agent_storage_dir),
            },
            'api_server': {
                'host': config.api_server_config.host,
                'port': config.api_server_config.port,
                'base_url': config.api_server_config.base_url,
            },
            'llm_models': {
                'llm_model': config.llm_config.model,
                'research_agent_model': config.research_agent_llm_config.model,
            },
            'discovery': {
                'auto_start_scheduler': config.discovery_config.auto_start_scheduler,
                'default_max_articles': config.discovery_config.default_max_articles,
            },
            'has_api_keys': {
                'mistral': bool(config.api_keys.mistral_key),
                'openrouter': bool(config.api_keys.openrouter_key),
            },
        }

        return JSONResponse(sanitized_config)

    except Exception as e:
        logger.error(f'Error getting agent config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get config: {e!s}'
        ) from e


@app.post('/agent/config')
async def update_agent_config(request: ConfigUpdateRequest):
    """Update agent configuration dynamically."""
    try:
        # Update environment variables
        env_updates = {}

        # Handle API keys
        if request.api_keys:
            for key, value in request.api_keys.items():
                if value:  # Only update non-empty values
                    env_key = f'API_{key.upper()}_KEY'
                    env_updates[env_key] = value
                    os.environ[env_key] = value

        # Handle directory settings
        if request.directories:
            for key, value in request.directories.items():
                if value:  # Only update non-empty values
                    env_key = key.upper() + '_DIR'
                    env_updates[env_key] = value
                    os.environ[env_key] = value

        # Handle other settings
        if request.settings:
            for key, value in request.settings.items():
                if value is not None:  # Allow False values
                    env_updates[key.upper()] = str(value)
                    os.environ[key.upper()] = str(value)

        logger.info(f'Updated environment variables: {list(env_updates.keys())}')

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Configuration updated successfully',
                'updated_keys': list(env_updates.keys()),
                'note': 'Agent restart required for changes to take full effect',
            }
        )

    except Exception as e:
        logger.error(f'Error updating agent config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to update config: {e!s}'
        ) from e


@app.post('/agent/restart')
async def restart_agent(request: AgentRestartRequest = None):
    """Restart the agent process."""
    try:
        # Update config if requested
        if request and request.update_config and request.new_config:
            await update_agent_config(request.new_config)

        # Get current process info
        current_pid = os.getpid()

        # For development/local mode, try to restart gracefully
        if hasattr(sys, '_called_from_test'):
            # In test mode, just reinitialize
            await reinitialize_agent()
            return JSONResponse(
                {
                    'status': 'success',
                    'message': 'Agent reinitialized successfully (test mode)',
                    'method': 'reinitialize',
                }
            )

        # Try to restart the process
        try:
            # Get the command line arguments
            python_executable = sys.executable
            script_args = sys.argv

            logger.info(f'Restarting agent process (PID: {current_pid})')
            logger.info(f'Command: {python_executable} {" ".join(script_args)}')

            # Start new process
            subprocess.Popen([python_executable, *script_args])

            # Send response before terminating
            response_data = {
                'status': 'success',
                'message': 'Agent restart initiated',
                'old_pid': current_pid,
                'method': 'process_restart',
            }

            # Schedule process termination after response
            import asyncio

            asyncio.create_task(delayed_shutdown())  # noqa: RUF006

            return JSONResponse(response_data)

        except Exception as restart_error:
            logger.error(f'Process restart failed: {restart_error}')

            # Fallback to agent reinitialization
            await reinitialize_agent()
            return JSONResponse(
                {
                    'status': 'success',
                    'message': 'Agent reinitialized successfully (fallback)',
                    'method': 'reinitialize',
                    'restart_error': str(restart_error),
                }
            )

    except Exception as e:
        logger.error(f'Error restarting agent: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to restart agent: {e!s}'
        ) from e


async def delayed_shutdown():
    """Shutdown the process after a short delay."""
    import asyncio

    await asyncio.sleep(1)  # Give time for response to be sent
    logger.info('Terminating process for restart...')
    os.kill(os.getpid(), signal.SIGTERM)


async def reinitialize_agent():
    """Reinitialize the agent without restarting the process."""
    global research_agent, agent_adapter, llm_router, service_manager

    try:
        logger.info('Reinitializing research agent...')

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
            f'Research agent reinitialized with {len(research_agent.get_available_tools())} tools'
        )

    except Exception as e:
        logger.error(f'Failed to reinitialize research agent: {e}')
        raise


@app.post('/agent/sync-settings')
async def sync_obsidian_settings(settings: dict[str, Any]):
    """Sync settings from Obsidian plugin to backend."""
    try:
        # Map Obsidian settings to environment variables
        env_updates = {}

        # API Keys
        if settings.get('mistralKey'):
            env_updates['API_MISTRAL_KEY'] = settings['mistralKey']
            os.environ['API_MISTRAL_KEY'] = settings['mistralKey']

        if settings.get('openrouterKey'):
            env_updates['API_OPENROUTER_KEY'] = settings['openrouterKey']
            os.environ['API_OPENROUTER_KEY'] = settings['openrouterKey']

        # Directories
        if settings.get('workspaceDirectory'):
            env_updates['WORKSPACE_DIR'] = settings['workspaceDirectory']
            os.environ['WORKSPACE_DIR'] = settings['workspaceDirectory']

        if settings.get('obsidianDirectory'):
            env_updates['NOTES_DIR'] = settings['obsidianDirectory']
            os.environ['NOTES_DIR'] = settings['obsidianDirectory']

        # Server settings
        if settings.get('endpointHost'):
            env_updates['ENDPOINT_HOST'] = settings['endpointHost']
            os.environ['ENDPOINT_HOST'] = settings['endpointHost']

        if settings.get('endpointPort'):
            env_updates['ENDPOINT_PORT'] = str(settings['endpointPort'])
            os.environ['ENDPOINT_PORT'] = str(settings['endpointPort'])

        logger.info(f'Synced settings from Obsidian: {list(env_updates.keys())}')

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Settings synced successfully',
                'synced_keys': list(env_updates.keys()),
            }
        )

    except Exception as e:
        logger.error(f'Error syncing Obsidian settings: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to sync settings: {e!s}'
        ) from e


# ============================================================================
# STREAMING & ENHANCED ENDPOINTS
# ============================================================================


@app.get('/operations/{operation_id}/status')
def get_operation_status_endpoint(operation_id: str):
    """Get the status of a long-running operation."""
    status = get_operation_status(operation_id)
    if status is None:
        raise HTTPException(status_code=404, detail='Operation not found')
    return JSONResponse(status)


@app.post('/stream/operation')
async def start_streaming_operation(request: StreamingOperationRequest):
    """Start a streaming operation and return operation ID for tracking."""
    import uuid

    operation_id = request.operation_id or str(uuid.uuid4())

    # Start the operation in background
    create_background_task(execute_streaming_operation(operation_id, request))

    return JSONResponse(
        {
            'operation_id': operation_id,
            'status': 'started',
            'message': f'Operation {request.operation_type} started',
        }
    )


async def execute_streaming_operation(
    operation_id: str, request: StreamingOperationRequest
):
    """Execute a streaming operation with progress updates."""
    try:
        update_operation_progress(
            operation_id, 'running', 0.0, f'Starting {request.operation_type}'
        )

        if request.operation_type == 'pdf_process':
            await stream_pdf_processing(operation_id, request.parameters)
        elif request.operation_type == 'discovery_run':
            await stream_discovery_run(operation_id, request.parameters)
        elif request.operation_type == 'batch_process':
            await stream_batch_process(operation_id, request.parameters)
        else:
            raise ValueError(f'Unknown operation type: {request.operation_type}')

        update_operation_progress(
            operation_id, 'completed', 100.0, 'Operation completed successfully'
        )

    except Exception as e:
        logger.error(f'Streaming operation {operation_id} failed: {e}')
        update_operation_progress(
            operation_id, 'failed', 0.0, f'Operation failed: {e!s}'
        )


async def stream_pdf_processing(operation_id: str, parameters: dict[str, Any]):
    """Stream PDF processing with progress updates."""
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    pdf_paths = parameters.get('pdf_paths', [])
    if not pdf_paths:
        raise ValueError('No PDF paths provided')

    total_pdfs = len(pdf_paths)

    for i, pdf_path in enumerate(pdf_paths):
        update_operation_progress(
            operation_id,
            'running',
            (i / total_pdfs) * 100,
            f'Processing PDF {i + 1}/{total_pdfs}: {Path(pdf_path).name}',
        )

        try:
            # Use the document pipeline to process PDF
            from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline

            pipeline = OptimizedDocumentPipeline(service_manager)

            result = await asyncio.to_thread(pipeline.process_pdf, Path(pdf_path))

            # Store result for this PDF
            update_operation_progress(
                operation_id,
                'running',
                ((i + 1) / total_pdfs) * 100,
                f'Completed PDF {i + 1}/{total_pdfs}',
                {'processed_pdfs': i + 1, 'latest_result': result},
            )

        except Exception as e:
            logger.error(f'Failed to process PDF {pdf_path}: {e}')
            update_operation_progress(
                operation_id,
                'running',
                ((i + 1) / total_pdfs) * 100,
                f'Failed to process PDF {i + 1}/{total_pdfs}: {e!s}',
            )


async def stream_discovery_run(operation_id: str, parameters: dict[str, Any]):
    """Stream discovery run with progress updates."""
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    source_name = parameters.get('source_name')
    max_articles = parameters.get('max_articles', 50)

    update_operation_progress(
        operation_id, 'running', 10.0, f'Starting discovery for source: {source_name}'
    )

    try:
        discovery_service = service_manager.get_service('discovery_service')
        if not discovery_service:
            raise ValueError('Discovery service not available')

        # Run discovery with progress callbacks
        def progress_callback(current: int, total: int, message: str = ''):
            progress = 10.0 + (current / total) * 80.0  # 10-90% for discovery
            update_operation_progress(operation_id, 'running', progress, message)

        # Execute discovery run
        results = await asyncio.to_thread(
            discovery_service.run_discovery_for_source,
            source_name,
            max_articles,
            progress_callback,
        )

        update_operation_progress(
            operation_id, 'running', 90.0, 'Discovery completed, processing results'
        )

        # Process and return results
        update_operation_progress(
            operation_id,
            'completed',
            100.0,
            f'Discovery completed: {len(results)} articles found',
            {'articles_found': len(results), 'results': results},
        )

    except Exception as e:
        logger.error(f'Discovery run failed: {e}')
        raise


async def stream_batch_process(operation_id: str, parameters: dict[str, Any]):
    """Stream batch processing with progress updates."""
    items = parameters.get('items', [])
    operation_type = parameters.get('operation_type', 'process')
    max_concurrent = parameters.get('max_concurrent', 3)

    if not items:
        raise ValueError('No items provided for batch processing')

    total_items = len(items)
    completed_items = 0

    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_item(item: dict[str, Any], index: int):
        nonlocal completed_items

        async with semaphore:
            try:
                update_operation_progress(
                    operation_id,
                    'running',
                    (completed_items / total_items) * 100,
                    f'Processing item {index + 1}/{total_items}',
                )

                # Process based on operation type
                if operation_type == 'pdf_process':
                    # Process PDF
                    result = await process_single_pdf(item)
                elif operation_type == 'discovery_query':
                    # Run discovery query
                    result = await process_discovery_query(item)
                else:
                    result = {'status': 'unknown_operation', 'item': item}

                completed_items += 1
                update_operation_progress(
                    operation_id,
                    'running',
                    (completed_items / total_items) * 100,
                    f'Completed item {index + 1}/{total_items}',
                    {'completed': completed_items, 'total': total_items},
                )

                return result

            except Exception as e:
                logger.error(f'Failed to process batch item {index}: {e}')
                completed_items += 1
                return {'status': 'failed', 'error': str(e), 'item': item}

    # Process all items concurrently
    tasks = [process_item(item, i) for i, item in enumerate(items)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return results


async def process_single_pdf(item: dict[str, Any]) -> dict[str, Any]:
    """Process a single PDF item."""
    pdf_path = item.get('path')
    if not pdf_path:
        raise ValueError('PDF path not provided')

    # Simulate PDF processing
    await asyncio.sleep(1)  # Replace with actual PDF processing
    return {'status': 'completed', 'path': pdf_path, 'result': 'processed'}


async def process_discovery_query(item: dict[str, Any]) -> dict[str, Any]:
    """Process a single discovery query."""
    query = item.get('query')
    if not query:
        raise ValueError('Query not provided')

    # Simulate discovery processing
    await asyncio.sleep(0.5)  # Replace with actual discovery processing
    return {'status': 'completed', 'query': query, 'results': []}


@app.post('/batch/process')
async def batch_process(request: BatchProcessRequest):
    """Process multiple items in batch with progress tracking."""
    import uuid

    operation_id = str(uuid.uuid4())

    # Start batch processing in background
    create_background_task(execute_batch_process(operation_id, request))

    return JSONResponse(
        {
            'operation_id': operation_id,
            'status': 'started',
            'total_items': len(request.items),
            'message': f'Batch processing started for {len(request.items)} items',
        }
    )


async def execute_batch_process(operation_id: str, request: BatchProcessRequest):
    """Execute batch processing operation."""
    try:
        parameters = {
            'items': request.items,
            'operation_type': request.operation_type,
            'max_concurrent': request.max_concurrent,
        }

        results = await stream_batch_process(operation_id, parameters)

        update_operation_progress(
            operation_id,
            'completed',
            100.0,
            f'Batch processing completed: {len(results)} items processed',
            {'results': results},
        )

    except Exception as e:
        logger.error(f'Batch processing {operation_id} failed: {e}')
        update_operation_progress(
            operation_id, 'failed', 0.0, f'Batch processing failed: {e!s}'
        )


@app.post('/execute/command')
async def execute_command(request: CommandExecutionRequest):
    """Execute a CLI command and optionally stream output."""
    import uuid

    operation_id = str(uuid.uuid4())

    if request.stream_output:
        # Start command execution in background for streaming
        create_background_task(execute_command_streaming(operation_id, request))

        return JSONResponse(
            {
                'operation_id': operation_id,
                'status': 'started',
                'streaming': True,
                'message': f'Command execution started: {request.command}',
            }
        )
    else:
        # Execute command synchronously
        try:
            result = await execute_command_sync(request)
            return JSONResponse(
                {'status': 'completed', 'result': result, 'streaming': False}
            )
        except Exception as e:
            logger.error(f'Command execution failed: {e}')
            raise HTTPException(
                status_code=500, detail=f'Command execution failed: {e!s}'
            ) from e


async def execute_command_streaming(
    operation_id: str, request: CommandExecutionRequest
):
    """Execute command with streaming progress updates."""
    try:
        update_operation_progress(
            operation_id, 'running', 0.0, f'Starting command: {request.command}'
        )

        # Map CLI commands to actual functions
        command_map = {
            'discovery': execute_discovery_command,
            'pdf-locate': execute_pdf_locate_command,
            'rag': execute_rag_command,
            'notes': execute_notes_command,
        }

        if request.command not in command_map:
            raise ValueError(f'Unknown command: {request.command}')

        # Execute the command
        result = await command_map[request.command](
            request.args, request.options, operation_id
        )

        update_operation_progress(
            operation_id,
            'completed',
            100.0,
            f'Command completed: {request.command}',
            result,
        )

    except Exception as e:
        logger.error(f'Command execution {operation_id} failed: {e}')
        update_operation_progress(operation_id, 'failed', 0.0, f'Command failed: {e!s}')


async def execute_command_sync(request: CommandExecutionRequest) -> dict[str, Any]:
    """Execute command synchronously and return result."""
    # This would integrate with the actual CLI commands
    # For now, return a placeholder
    return {
        'command': request.command,
        'args': request.args,
        'options': request.options,
        'result': 'Command executed successfully (placeholder)',
    }


async def execute_discovery_command(
    args: list[str], options: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    """Execute discovery CLI command."""
    update_operation_progress(
        operation_id, 'running', 25.0, 'Initializing discovery service'
    )

    if service_manager is None:
        raise ValueError('Service manager not initialized')

    discovery_service = service_manager.get_service('discovery_service')
    if not discovery_service:
        raise ValueError('Discovery service not available')

    # Handle different discovery subcommands
    if not args:
        subcommand = 'list'
    else:
        subcommand = args[0]

    update_operation_progress(
        operation_id, 'running', 50.0, f'Executing discovery {subcommand}'
    )

    if subcommand == 'list':
        sources = discovery_service.list_sources()
        return {'subcommand': 'list', 'sources': sources}
    elif subcommand == 'run':
        source_name = options.get('source')
        max_articles = options.get('max_articles', 50)
        results = await discovery_service.run_discovery_for_source(
            source_name, max_articles
        )
        return {'subcommand': 'run', 'source': source_name, 'results': results}
    else:
        return {'subcommand': subcommand, 'result': f'Discovery {subcommand} executed'}


async def execute_pdf_locate_command(
    args: list[str], options: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    """Execute PDF locate CLI command."""
    update_operation_progress(operation_id, 'running', 50.0, 'Locating PDF sources')

    doi = args[0] if args else options.get('doi')
    if not doi:
        raise ValueError('DOI is required for PDF locate')

    # Simulate PDF location
    await asyncio.sleep(1)

    return {'doi': doi, 'sources_found': ['arxiv', 'unpaywall'], 'pdf_available': True}


async def execute_rag_command(
    args: list[str], options: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    """Execute RAG CLI command."""
    if not args:
        subcommand = 'stats'
    else:
        subcommand = args[0]

    update_operation_progress(
        operation_id, 'running', 50.0, f'Executing RAG {subcommand}'
    )

    if subcommand == 'search':
        query = options.get('query', '')
        return {'subcommand': 'search', 'query': query, 'results': []}
    elif subcommand == 'index':
        return {'subcommand': 'index', 'indexed_documents': 0}
    else:
        return {'subcommand': subcommand, 'result': f'RAG {subcommand} executed'}


async def execute_notes_command(
    args: list[str], _options: dict[str, Any], operation_id: str
) -> dict[str, Any]:
    """Execute notes CLI command."""
    if not args:
        subcommand = 'regenerate-all-notes'
    else:
        subcommand = args[0]

    update_operation_progress(
        operation_id, 'running', 50.0, f'Executing notes {subcommand}'
    )

    return {'subcommand': subcommand, 'result': f'Notes {subcommand} executed'}


@app.post('/tools/execute')
async def execute_tool_direct(request: ToolExecutionRequest):
    """Execute a specific tool directly, optionally bypassing the agent."""
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        if request.bypass_agent:
            # Execute tool directly
            tools = research_agent.get_available_tools()
            tool_info = next(
                (t for t in tools if t.get('name') == request.tool_name), None
            )

            if not tool_info:
                raise HTTPException(
                    status_code=404, detail=f'Tool {request.tool_name} not found'
                )

            # Execute the tool (implementation based on tool structure)
            result = await execute_tool_directly(request.tool_name, request.parameters)

            return JSONResponse(
                {
                    'tool': request.tool_name,
                    'parameters': request.parameters,
                    'result': result,
                    'bypassed_agent': True,
                }
            )
        else:
            # Execute through agent
            message = f'Please use the {request.tool_name} tool with these parameters: {request.parameters}'
            response = await research_agent.chat(
                message=message, session_id=f'tool-execution-{int(time.time())}'
            )

            return JSONResponse(
                {
                    'tool': request.tool_name,
                    'parameters': request.parameters,
                    'response': response.get('response'),
                    'tool_calls': response.get('tool_calls', []),
                    'bypassed_agent': False,
                }
            )

    except Exception as e:
        logger.error(f'Tool execution failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Tool execution failed: {e!s}'
        ) from e


async def execute_tool_directly(
    tool_name: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    """Execute a tool directly without going through the agent."""
    # This would need to be implemented based on the actual tool architecture
    # For now, return a placeholder
    return {
        'tool_executed': tool_name,
        'parameters_used': parameters,
        'result': f'Tool {tool_name} executed directly (placeholder)',
        'timestamp': time.time(),
    }


# ============================================================================
# CONFIGURATION VALIDATION & MANAGEMENT ENDPOINTS
# ============================================================================


@app.get('/config/export')
def export_config_for_obsidian():
    """Export current configuration in Obsidian plugin format."""
    try:
        config = get_config()
        obsidian_config = config.export_for_obsidian()

        return JSONResponse(
            {
                'status': 'success',
                'config': obsidian_config,
                'config_version': '1.0.0',
                'exported_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Failed to export config for Obsidian: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config export failed: {e!s}'
        ) from e


@app.post('/config/import')
async def import_config_from_obsidian(obsidian_config: dict[str, Any]):
    """Import configuration from Obsidian plugin format and validate it."""
    try:
        from thoth.utilities.config import ThothConfig

        # Import configuration from Obsidian format
        imported_config = ThothConfig.import_from_obsidian(obsidian_config)

        # Validate the imported configuration
        validation_result = imported_config.validate_for_obsidian()

        if validation_result['errors']:
            return JSONResponse(
                {
                    'status': 'validation_failed',
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings'],
                    'message': 'Configuration validation failed',
                },
                status_code=400,
            )

        # If validation passed, sync to environment
        synced_vars = imported_config.sync_to_environment()

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Configuration imported and validated successfully',
                'synced_environment_vars': list(synced_vars.keys()),
                'warnings': validation_result['warnings'],
                'imported_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Failed to import config from Obsidian: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config import failed: {e!s}'
        ) from e


@app.post('/config/validate')
async def validate_config(config_data: dict[str, Any] | None = None):
    """Validate configuration data (current or provided) for Obsidian integration."""
    try:
        from thoth.utilities.config import ThothConfig

        if config_data:
            # Validate provided configuration
            test_config = ThothConfig.import_from_obsidian(config_data)
            validation_result = test_config.validate_for_obsidian()
            source = 'provided'
        else:
            # Validate current configuration
            current_config = get_config()
            validation_result = current_config.validate_for_obsidian()
            source = 'current'

        is_valid = len(validation_result['errors']) == 0

        return JSONResponse(
            {
                'status': 'valid' if is_valid else 'invalid',
                'source': source,
                'is_valid': is_valid,
                'errors': validation_result['errors'],
                'warnings': validation_result['warnings'],
                'error_count': len(validation_result['errors']),
                'warning_count': len(validation_result['warnings']),
                'validated_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Config validation failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config validation failed: {e!s}'
        ) from e


@app.get('/config/schema')
def get_config_schema():
    """Get the configuration schema for the Obsidian plugin."""
    schema = {
        'version': '1.0.0',
        'sections': {
            'api_keys': {
                'title': 'API Keys',
                'description': 'External service API keys',
                'fields': {
                    'mistralKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'openrouterKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'opencitationsKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'googleApiKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'semanticScholarKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'webSearchKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                },
            },
            'directories': {
                'title': 'Directory Configuration',
                'description': 'File system paths',
                'fields': {
                    'workspaceDirectory': {'type': 'path', 'required': True},
                    'obsidianDirectory': {'type': 'path', 'required': True},
                    'pdfDirectory': {'type': 'path', 'required': False},
                    'promptsDirectory': {'type': 'path', 'required': False},
                },
            },
            'connection': {
                'title': 'Connection Settings',
                'description': 'Server connection configuration',
                'fields': {
                    'remoteMode': {
                        'type': 'boolean',
                        'required': False,
                        'default': False,
                    },
                    'endpointHost': {
                        'type': 'string',
                        'required': False,
                        'default': '127.0.0.1',
                    },
                    'endpointPort': {
                        'type': 'integer',
                        'required': False,
                        'default': 8000,
                        'min': 1024,
                        'max': 65535,
                    },
                    'remoteEndpointUrl': {'type': 'string', 'required': False},
                },
            },
            'llm': {
                'title': 'Language Model Configuration',
                'description': 'LLM settings and parameters',
                'fields': {
                    'primaryLlmModel': {
                        'type': 'string',
                        'required': False,
                        'default': 'anthropic/claude-3-sonnet',
                    },
                    'llmTemperature': {
                        'type': 'number',
                        'required': False,
                        'default': 0.7,
                        'min': 0.0,
                        'max': 1.0,
                    },
                    'llmMaxOutputTokens': {
                        'type': 'integer',
                        'required': False,
                        'default': 4096,
                        'min': 1,
                    },
                },
            },
            'agent': {
                'title': 'Agent Behavior',
                'description': 'Research agent configuration',
                'fields': {
                    'agentMaxToolCalls': {
                        'type': 'integer',
                        'required': False,
                        'default': 20,
                        'min': 1,
                    },
                    'agentTimeoutSeconds': {
                        'type': 'integer',
                        'required': False,
                        'default': 300,
                        'min': 30,
                    },
                    'researchAgentMemoryEnabled': {
                        'type': 'boolean',
                        'required': False,
                        'default': True,
                    },
                },
            },
            'discovery': {
                'title': 'Discovery System',
                'description': 'Research discovery configuration',
                'fields': {
                    'discoveryDefaultMaxArticles': {
                        'type': 'integer',
                        'required': False,
                        'default': 50,
                        'min': 1,
                    },
                    'discoveryDefaultIntervalMinutes': {
                        'type': 'integer',
                        'required': False,
                        'default': 60,
                        'min': 15,
                    },
                    'discoveryRateLimitDelay': {
                        'type': 'number',
                        'required': False,
                        'default': 1.0,
                        'min': 0.1,
                    },
                },
            },
        },
        'validation_rules': {
            'required_api_keys': 'At least one of mistralKey or openrouterKey must be provided',
            'directory_existence': 'Workspace and Obsidian directories should exist',
            'port_range': 'Endpoint port must be between 1024 and 65535',
            'temperature_range': 'LLM temperature must be between 0.0 and 1.0',
        },
    }

    return JSONResponse(schema)


@app.get('/config/defaults')
def get_config_defaults():
    """Get default configuration values for the Obsidian plugin."""
    from thoth.utilities.config import ThothConfig

    try:
        # Create a default config instance
        default_config = ThothConfig()

        # Export to Obsidian format to get defaults
        defaults = default_config.export_for_obsidian()

        return JSONResponse(
            {'status': 'success', 'defaults': defaults, 'generated_at': time.time()}
        )

    except Exception as e:
        logger.error(f'Failed to get config defaults: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get defaults: {e!s}'
        ) from e


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

    Args:
        host (str): Host to bind the server to.
        port (int): Port to bind the server to.
        pdf_directory (Path): Directory where PDFs will be stored.
        notes_directory (Path): Directory where notes are stored (Obsidian vault).
        api_base_url (str): Base URL for the API.
        pipeline (ThothPipeline | None): Optional ThothPipeline instance.
        reload (bool): Whether to enable auto-reload for development.
    """
    global \
        pdf_dir, \
        notes_dir, \
        base_url, \
        research_agent, \
        agent_adapter, \
        llm_router, \
        service_manager, \
        chat_manager

    # Set module-level configuration
    pdf_dir = pdf_directory
    notes_dir = notes_directory
    base_url = api_base_url

    logger.info(f'Starting Obsidian API server on {host}:{port}')
    logger.info(f'PDF directory: {pdf_dir}')
    logger.info(f'Notes directory: {notes_dir}')
    logger.info(f'API base URL: {base_url}')

    # Initialize chat persistence manager
    try:
        logger.info('Initializing chat persistence manager...')
        config = get_config()
        chat_storage_path = config.agent_storage_dir / 'chat_sessions'
        chat_manager = ChatPersistenceManager(chat_storage_path)
        logger.info(f'Chat persistence initialized at: {chat_storage_path}')
    except Exception as e:
        logger.error(f'Failed to initialize chat persistence: {e}')
        logger.warning('Server will start without chat persistence functionality')

    # Initialize the research agent and MCP server
    try:
        logger.info('Initializing research agent...')
        from thoth.ingestion.agent_v2 import create_research_assistant_async

        # Use provided pipeline or create a new one
        if pipeline is None:
            from thoth.pipeline import ThothPipeline

            pipeline = ThothPipeline()

        service_manager = pipeline.services

        # Start MCP server in background
        logger.info('Starting MCP server...')
        await _start_mcp_server_background()

        # Create the research agent with async initialization
        research_agent = await create_research_assistant_async(
            service_manager=service_manager,
            enable_memory=True,
        )

        # Initialize router
        config = get_config()
        llm_router = LLMRouter(config)

        logger.info(
            f'Research agent initialized with {len(research_agent.tools)} tools'
        )

    except Exception as e:
        logger.error(f'Failed to initialize research agent: {e}')
        logger.warning('Server will start without research agent functionality')

    # Start the uvicorn server with proper signal handling
    config = uvicorn.Config(app, host=host, port=port, reload=reload)
    server = uvicorn.Server(config)

    # Set up signal handlers for graceful shutdown
    import asyncio
    import signal

    shutdown_event = asyncio.Event()

    def signal_handler(signum, _frame):
        logger.info(f'Received signal {signum}, initiating graceful shutdown...')
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start server in background
        server_task = asyncio.create_task(server.serve())

        # Wait for either server completion or shutdown signal
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If shutdown was requested, gracefully stop the server
        if shutdown_event.is_set():
            logger.info('Shutting down server gracefully...')

            # First shutdown background tasks and MCP server
            await shutdown_background_tasks(timeout=5.0)
            await shutdown_mcp_server(timeout=5.0)

            # Then shutdown the main server
            server.should_exit = True

            # Wait for server to complete shutdown gracefully
            try:
                await asyncio.wait_for(server_task, timeout=30.0)
            except TimeoutError:
                logger.warning('Server shutdown timeout, forcing termination')
                server_task.cancel()
                try:
                    await server_task
                except asyncio.CancelledError:
                    logger.info('Server task cancelled during forced shutdown')

        # Cancel any remaining tasks (shutdown_task if server completed first)
        for task in pending:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug('Pending task cancelled during shutdown')
                except Exception as e:
                    logger.warning(f'Error cancelling pending task: {e}')

    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt received, shutting down gracefully...')

        # First shutdown background tasks and MCP server
        await shutdown_background_tasks(timeout=3.0)
        await shutdown_mcp_server(timeout=3.0)

        # Then shutdown the main server
        server.should_exit = True

        # Give server time to shutdown gracefully
        try:
            await asyncio.wait_for(server_task, timeout=10.0)
        except TimeoutError:
            logger.warning('Server shutdown timeout after KeyboardInterrupt')
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                logger.info('Server task cancelled after KeyboardInterrupt')
        except Exception as e:
            logger.error(f'Error during shutdown: {e}')

    except Exception as e:
        logger.error(f'Unexpected error in server main loop: {e}', exc_info=True)

        # Emergency shutdown with proper error handling
        try:
            await shutdown_background_tasks(timeout=2.0)
        except Exception as shutdown_error:
            logger.error(
                f'Error during emergency background task shutdown: {shutdown_error}'
            )

        try:
            await shutdown_mcp_server(timeout=2.0)
        except Exception as shutdown_error:
            logger.error(
                f'Error during emergency MCP server shutdown: {shutdown_error}'
            )

        # Force shutdown the main server
        server.should_exit = True
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            logger.info('Server task cancelled during emergency shutdown')
        except Exception as server_error:
            logger.error(f'Error during emergency server shutdown: {server_error}')


async def _start_mcp_server_background() -> None:
    """Start the MCP server in the background."""
    import asyncio

    from thoth.mcp.launcher import launch_mcp_server

    # Start MCP server using configured port from settings
    config = get_config()
    mcp_port = config.mcp_port
    mcp_host = config.mcp_host

    # Start MCP server as a background task
    async def _mcp_task_wrapper():
        """Wrapper to handle MCP server task exceptions."""
        try:
            await launch_mcp_server(
                stdio=False,
                http=True,
                http_host=mcp_host,
                http_port=mcp_port,
                sse=False,
            )
        except asyncio.CancelledError:
            logger.info('MCP server task cancelled gracefully')
            raise  # Re-raise to ensure proper cancellation handling
        except Exception as e:
            logger.error(f'MCP server failed: {e}')
            raise  # Re-raise to prevent silent failures

    # Create and start the background task
    mcp_task = asyncio.create_task(_mcp_task_wrapper())

    # Add the task to a global set to prevent it from being garbage collected
    # and to suppress the "unawaited coroutine" warning
    if not hasattr(_start_mcp_server_background, '_background_tasks'):
        _start_mcp_server_background._background_tasks = set()
    _start_mcp_server_background._background_tasks.add(mcp_task)

    # Remove completed tasks from the set
    mcp_task.add_done_callback(_start_mcp_server_background._background_tasks.discard)

    # Give the MCP server a moment to start
    await asyncio.sleep(1)
    logger.info(f'MCP server started on http://{mcp_host}:{mcp_port}/mcp')


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

    This function handles the async initialization and then starts the server.
    """
    import asyncio

    async def _async_start():
        await start_server(
            host=host,
            port=port,
            pdf_directory=pdf_directory,
            notes_directory=notes_directory,
            api_base_url=api_base_url,
            pipeline=pipeline,
            reload=reload,
        )

    # Run the async initialization
    asyncio.run(_async_start())


if __name__ == '__main__':
    # This is for development purposes only
    import asyncio
    from pathlib import Path

    asyncio.run(
        start_server(
            '127.0.0.1',
            8000,
            Path('./data/pdf'),
            Path('./data/notes'),
            'http://127.0.0.1:8000',
        )
    )
