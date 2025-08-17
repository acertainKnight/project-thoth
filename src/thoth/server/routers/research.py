"""
Research and chat endpoints.
"""

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

from thoth.server.chat_models import ChatManager, ChatMessage
from thoth.services.llm_router import LLMRouter
from thoth.utilities.config import get_config

router = APIRouter(prefix="/research", tags=["research"])


def get_chat_manager() -> ChatManager:
    """Get chat manager from app state."""
    from thoth.server.app import app
    
    if not hasattr(app.state, 'chat_manager'):
        raise HTTPException(status_code=503, detail='Chat manager not initialized')
    return app.state.chat_manager


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str
    session_id: str | None = None
    model: str | None = None


class ResearchRequest(BaseModel):
    """Request model for research queries."""
    query: str
    sources: list[str] | None = None
    max_results: int = 10
    include_citations: bool = True


@router.post('/chat')
async def research_chat(
    request: ChatRequest,
    research_agent=None,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    Chat with the research agent.
    
    This endpoint provides a synchronous interface to the research agent,
    with optional chat history persistence.
    """
    if research_agent is None:
        raise HTTPException(
            status_code=503, detail='Research agent not initialized'
        )

    try:
        # If no session_id provided, create one
        if request.session_id is None:
            request.session_id = f'api-{datetime.now().isoformat()}'

        # Determine which model to use
        model_to_use = request.model
        if not model_to_use:
            config = get_config()
            router = LLMRouter(config)
            model_to_use = router.select_model(request.message)

        # Store user message if chat manager is available
        user_message_id = None
        if chat_manager is not None:
            try:
                # Ensure session exists
                existing_session = chat_manager.get_session(request.session_id)
                if not existing_session:
                    # Auto-generate title from first message
                    title = (
                        request.message[:50] + '...'
                        if len(request.message) > 50
                        else request.message
                    )
                    chat_manager.create_session(
                        session_id=request.session_id,
                        title=title,
                        metadata={'source': 'api'},
                    )

                # Store user message
                user_message = ChatMessage(
                    session_id=request.session_id,
                    role='user',
                    content=request.message,
                    metadata={'source': 'api'},
                )
                chat_manager.add_message(user_message)
                user_message_id = user_message.id
            except Exception as e:
                logger.warning(f'Failed to store user message: {e}')

        # Get response from research agent
        response = await research_agent.chat(
            message=request.message,
            session_id=request.session_id,
            model_override=model_to_use,
        )

        agent_response = response.get('response', 'No response generated')
        tool_calls = response.get('tool_calls', [])

        # Store assistant response if chat manager is available
        if chat_manager is not None and user_message_id:
            try:
                assistant_message = ChatMessage(
                    session_id=request.session_id,
                    role='assistant',
                    content=agent_response,
                    tool_calls=tool_calls,
                    metadata={'model': model_to_use, 'source': 'api'},
                    parent_message_id=user_message_id,
                )
                chat_manager.add_message(assistant_message)
            except Exception as e:
                logger.warning(f'Failed to store assistant message: {e}')

        return JSONResponse(
            {
                'status': 'success',
                'session_id': request.session_id,
                'response': agent_response,
                'model_used': model_to_use,
                'tool_calls': tool_calls,
            }
        )

    except Exception as e:
        logger.error(f'Error in research chat: {e}')
        raise HTTPException(
            status_code=500, detail=f'Chat request failed: {e!s}'
        ) from e


@router.post('/query')
async def research_query(
    request: ResearchRequest,
    research_agent=None
):
    """
    Execute a research query with specified sources.
    
    This endpoint allows for more structured research queries with
    specific source selection and result filtering.
    """
    if research_agent is None:
        raise HTTPException(
            status_code=503, detail='Research agent not initialized'
        )

    try:
        # Build the research prompt
        prompt = f"Research query: {request.query}"
        if request.sources:
            prompt += f"\nPlease focus on these sources: {', '.join(request.sources)}"
        prompt += f"\nReturn up to {request.max_results} results."
        if request.include_citations:
            prompt += "\nInclude full citations for all sources."

        # Execute the research
        session_id = f'research-{datetime.now().isoformat()}'
        response = await research_agent.chat(
            message=prompt,
            session_id=session_id,
        )

        return JSONResponse(
            {
                'status': 'success',
                'query': request.query,
                'response': response.get('response', ''),
                'tool_calls': response.get('tool_calls', []),
                'sources_used': request.sources,
                'session_id': session_id,
            }
        )

    except Exception as e:
        logger.error(f'Error in research query: {e}')
        raise HTTPException(
            status_code=500, detail=f'Research query failed: {e!s}'
        ) from e