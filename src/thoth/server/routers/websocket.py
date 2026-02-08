"""WebSocket endpoints for real-time communication."""

import asyncio
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger

from thoth.server.dependencies import (
    get_chat_manager,
    get_research_agent,
)

router = APIRouter()

# REMOVED: Module-level globals - Phase 5
# Dependencies now injected via FastAPI Depends() instead of set_dependencies()
# Note: WebSocket endpoints get dependencies directly in their signature


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


# WebSocket connection managers
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


@router.websocket('/ws/chat')
async def websocket_chat(
    websocket: WebSocket,
    research_agent=Depends(get_research_agent),
    chat_manager=Depends(get_chat_manager),
) -> None:
    """
    WebSocket endpoint for real-time chat with the research agent.

    This endpoint allows for bidirectional communication with the research agent,
    enabling real-time conversation and tool usage.
    """
    await chat_ws_manager.connect(websocket)
    logger.info('WebSocket chat connection established')

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if not research_agent:
                await websocket.send_json(
                    {
                        'error': 'Research agent not initialized',
                        'type': 'error',
                    }
                )
                continue

            message = data.get('message', '')
            session_id = data.get('session_id')
            message_id = data.get('id')

            if not message:
                error_response = {
                    'error': 'Message is required',
                    'type': 'error',
                }
                if message_id:
                    error_response['id'] = message_id
                await websocket.send_json(error_response)
                continue

            try:
                # Process message with research agent
                response = await research_agent.chat(
                    message=message,
                    session_id=session_id,
                )

                # Save to chat history if we have a chat manager
                if chat_manager and session_id:
                    await chat_manager.save_message(
                        session_id=session_id,
                        role='user',
                        content=message,
                    )

                    await chat_manager.save_message(
                        session_id=session_id,
                        role='assistant',
                        content=response.get('response', ''),
                    )

                # Send response back to client
                response_data = {
                    'response': response.get('response', ''),
                    'tool_calls': response.get('tool_calls', []),
                    'type': 'response',
                }
                if message_id:
                    response_data['id'] = message_id
                await websocket.send_json(response_data)

            except Exception as e:
                logger.error(f'Error processing chat message: {e}')
                error_response = {
                    'error': f'Error processing message: {e}',
                    'type': 'error',
                }
                if message_id:
                    error_response['id'] = message_id
                await websocket.send_json(error_response)

    except WebSocketDisconnect:
        logger.info('WebSocket chat connection closed')
    except Exception as e:
        logger.error(f'WebSocket chat error: {e}')
    finally:
        chat_ws_manager.disconnect(websocket)


@router.websocket('/ws/status')
async def websocket_status(websocket: WebSocket) -> None:
    """WebSocket endpoint for system status updates."""
    await status_ws_manager.connect(websocket)
    logger.info('WebSocket status connection established')

    try:
        # Send initial status
        await websocket.send_json({'status': 'running'})

        while True:
            await asyncio.sleep(1)  # Keep connection alive
    except WebSocketDisconnect:
        logger.info('WebSocket status connection closed')
    finally:
        status_ws_manager.disconnect(websocket)


@router.websocket('/ws/progress')
async def websocket_progress(websocket: WebSocket) -> None:
    """WebSocket endpoint for operation progress updates."""
    await progress_ws_manager.connect(websocket)
    logger.info('WebSocket progress connection established')

    try:
        while True:
            await asyncio.sleep(1)  # Keep connection alive
    except WebSocketDisconnect:
        logger.info('WebSocket progress connection closed')
    finally:
        progress_ws_manager.disconnect(websocket)
