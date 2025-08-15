"""
WebSocket endpoints for real-time communication.
"""

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from thoth.server.chat_models import ChatManager, ChatMessage
from thoth.services.llm_router import LLMRouter
from thoth.utilities.config import get_config

router = APIRouter(tags=["websocket"])


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


# Create connection managers
chat_ws_manager = ConnectionManager()
status_ws_manager = ConnectionManager()
progress_ws_manager = ConnectionManager()


@router.websocket('/ws/chat')
async def websocket_chat(
    websocket: WebSocket,
    research_agent=None,
    chat_manager: ChatManager | None = None
) -> None:
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
            router_instance = LLMRouter(config)
            model = router_instance.select_model(message)
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


@router.websocket('/ws/status')
async def websocket_status(websocket: WebSocket, research_agent=None) -> None:
    """WebSocket endpoint for status updates."""
    await status_ws_manager.connect(websocket)
    try:
        while True:
            status = 'running' if research_agent else 'not_initialized'
            await websocket.send_json({'status': status})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        status_ws_manager.disconnect(websocket)


@router.websocket('/ws/progress')
async def websocket_progress(websocket: WebSocket) -> None:
    """WebSocket endpoint for progress notifications."""
    await progress_ws_manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        progress_ws_manager.disconnect(websocket)


# Export connection managers for use by other modules
__all__ = [
    'router',
    'chat_ws_manager',
    'status_ws_manager', 
    'progress_ws_manager',
    'ConnectionManager',
]