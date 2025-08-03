from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel

from thoth.ingestion.agent_adapter import AgentAdapter
from thoth.ingestion.agent_v2 import create_research_assistant

app = FastAPI(
    title='Thoth MCP Server',
    description='Local server exposing the research assistant via MCP style endpoints',
    version='0.1.0',
)

agent: Any | None = None


class ChatMessage(BaseModel):
    """Single chat message following MCP format."""

    role: Literal['user', 'assistant', 'tool', 'system']
    content: str
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str | None = None
    messages: list[ChatMessage] | None = None
    session_id: str | None = None
    context: dict[str, Any] | None = None


@app.on_event('startup')
def startup_event() -> None:
    """Initialize pipeline and research assistant when the server starts."""
    global agent
    # Import here to avoid circular import
    from thoth.pipeline import ThothPipeline

    pipeline = ThothPipeline()
    adapter = AgentAdapter(pipeline.services)
    agent = create_research_assistant(
        adapter=adapter, enable_memory=True, use_mcp_tools=True
    )
    logger.info('MCP server initialized successfully')


@app.post('/chat')
async def chat(request: ChatRequest) -> dict[str, Any]:
    """Chat with the research assistant."""
    assert agent is not None, 'Agent not initialized'
    if request.messages:
        return await agent.chat_messages(
            messages=[msg.model_dump() for msg in request.messages],
            session_id=request.session_id,
            context=request.context,
        )
    if request.message:
        return await agent.chat(
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        )
    raise HTTPException(status_code=400, detail='No message provided')


@app.get('/tools')
def list_tools() -> list[dict[str, str]]:
    """Return information about available tools."""
    assert agent is not None, 'Agent not initialized'
    return agent.get_available_tools()


@app.get('/health')
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'ok'}


def start_mcp_server(host: str, port: int) -> None:
    """Run the MCP server with uvicorn."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
