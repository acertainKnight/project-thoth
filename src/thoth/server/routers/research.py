"""Research and chat endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.config import config
from thoth.server.dependencies import get_research_agent
from thoth.services.llm_router import LLMRouter

router = APIRouter()

# Module-level globals removed; services injected via FastAPI Depends()
# Dependencies now injected via FastAPI Depends() instead of set_dependencies()


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
    max_results: int = 10
    sources: list[str] = []
    context: dict[str, Any] = {}


class ResearchResponse(BaseModel):
    results: list[dict[str, Any]]
    summary: str
    sources_used: list[str]
    query: str


@router.post('/chat')
async def research_chat(
    request: ChatRequest,
    research_agent=Depends(get_research_agent),
    _user_context: UserContext = Depends(get_user_context),
) -> ChatResponse:
    """
    Chat endpoint that delegates to the legacy in-process research agent.

    Chat persistence is handled entirely by Letta; this endpoint only
    forwards the message and returns the response.

    Args:
        request: Chat request containing message and conversation context.

    Returns:
        ChatResponse with the agent's reply.
    """
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        llm_router = LLMRouter(config)
        selected_model = llm_router.select_model(request.message)

        session_id = (
            request.conversation_id
            or f'obsidian-{request.timestamp or int(datetime.now().timestamp())}'
        )

        response = await research_agent.chat(
            message=request.message,
            session_id=session_id,
            model_override=selected_model,
        )

        agent_response = response.get('response', 'No response generated')
        tool_calls = response.get('tool_calls', [])

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


@router.post('/query')
async def research_query(
    request: ResearchRequest,
    research_agent=Depends(get_research_agent),
    _user_context: UserContext = Depends(get_user_context),
) -> ResearchResponse:
    """
    Direct research query endpoint for quick research tasks.

    Args:
        request: Research request with query and parameters.

    Returns:
        ResearchResponse with results and analysis.
    """
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        # Use the research agent to process the query
        response = await research_agent.chat(
            message=f'Research query: {request.query}. Please search for relevant papers and provide analysis.',
            context=request.context,
        )

        # Extract results from the agent response
        # Note: This is a simplified implementation - in practice, you'd parse
        # the agent response to extract structured results
        results = []
        if 'tool_calls' in response:
            # Process any tool calls to extract structured data
            for tool_call in response.get('tool_calls', []):
                if tool_call.get('tool') in [
                    'thoth_search_papers',
                    'thoth_analyze_document',
                ]:
                    results.append(
                        {
                            'tool': tool_call.get('tool'),
                            'arguments': tool_call.get('args', {}),
                            'result': 'Tool execution result would be here',
                        }
                    )

        # Generate summary from agent response
        summary = response.get('response', 'No summary available')

        # Extract sources mentioned in the response
        sources_used = request.sources if request.sources else ['thoth_knowledge_base']

        return ResearchResponse(
            results=results,
            summary=summary,
            sources_used=sources_used,
            query=request.query,
        )

    except Exception as e:
        logger.error(f'Error in research query: {e}')
        raise HTTPException(
            status_code=500, detail=f'Research query failed: {e!s}'
        ) from e
