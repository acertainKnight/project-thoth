"""
Chat sessions and messages endpoints.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Depends
from loguru import logger
from pydantic import BaseModel

from thoth.server.chat_models import ChatManager

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_manager() -> ChatManager:
    """Get chat manager from app state."""
    from thoth.server.app import app
    
    if not hasattr(app.state, 'chat_manager'):
        raise HTTPException(status_code=503, detail='Chat manager not initialized')
    return app.state.chat_manager


# Request/Response models
class CreateSessionRequest(BaseModel):
    title: str
    metadata: dict[str, Any] | None = None


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


@router.post('/sessions')
async def create_chat_session(
    request: CreateSessionRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> dict[str, Any]:
    """Create a new chat session."""
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


@router.get('/sessions')
async def list_chat_sessions(
    active_only: bool = True,
    limit: int = 50,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> SessionListResponse:
    """List chat sessions."""
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


@router.get('/sessions/{session_id}')
async def get_chat_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> dict[str, Any]:
    """Get a specific chat session."""
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


@router.put('/sessions/{session_id}')
async def update_chat_session(
    session_id: str,
    request: UpdateSessionRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> dict[str, Any]:
    """Update a chat session."""
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


@router.delete('/sessions/{session_id}')
async def delete_chat_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> dict[str, Any]:
    """Delete a chat session and all its messages."""
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


@router.post('/sessions/{session_id}/archive')
async def archive_chat_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> dict[str, Any]:
    """Archive a chat session (mark as inactive)."""
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


@router.get('/sessions/{session_id}/messages')
async def get_chat_history(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> MessageHistoryResponse:
    """Get chat history for a session."""
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


@router.get('/search')
async def search_chat_messages(
    query: str,
    session_id: str | None = None,
    limit: int = 50,
    chat_manager: ChatManager = Depends(get_chat_manager)
) -> dict[str, Any]:
    """Search chat messages by content."""
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