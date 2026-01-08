"""
Agent proxy endpoints for Letta integration.

This module provides optional convenience endpoints for interacting with
Letta agents. Direct Letta REST API access is recommended for advanced usage.

All agent management is now handled by the Letta platform running on port 8283.
"""

import os
from typing import Any  # noqa: F401

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from thoth.config import config

router = APIRouter()

# Letta configuration
LETTA_BASE_URL = os.getenv('LETTA_BASE_URL', 'http://localhost:8283')
LETTA_API_KEY = os.getenv('LETTA_SERVER_PASS', '')


class ChatMessage(BaseModel):
    """Chat message request model."""

    message: str
    conversation_id: str | None = None
    user_id: str = 'default'
    agent_name: str | None = None


class AgentCreateRequest(BaseModel):
    """Request model for creating a new Letta agent."""

    name: str
    description: str | None = None
    tools: list[str] | None = None
    system_prompt: str | None = None


@router.get('/status')
def agent_status():
    """
    Check Letta agent service status.

    Returns health status of the Letta platform.
    """
    try:
        import httpx

        # Check if Letta is accessible
        response = httpx.get(f'{LETTA_BASE_URL}/health', timeout=5.0)

        if response.status_code == 200:
            return JSONResponse(
                {
                    'status': 'running',
                    'platform': 'letta',
                    'base_url': LETTA_BASE_URL,
                    'message': 'Letta platform is running and accessible',
                }
            )
        else:
            return JSONResponse(
                {
                    'status': 'degraded',
                    'platform': 'letta',
                    'base_url': LETTA_BASE_URL,
                    'message': f'Letta returned status {response.status_code}',
                },
                status_code=503,
            )

    except ImportError:
        return JSONResponse(
            {
                'status': 'error',
                'message': 'httpx not installed. Install with: pip install httpx',
            },
            status_code=500,
        )
    except Exception as e:
        logger.error(f'Error checking Letta status: {e}')
        return JSONResponse(
            {
                'status': 'unavailable',
                'platform': 'letta',
                'base_url': LETTA_BASE_URL,
                'error': str(e),
                'message': 'Cannot connect to Letta platform',
            },
            status_code=503,
        )


@router.get('/list')
async def list_available_agents():
    """
    List all available Letta agents.

    This is a convenience endpoint. For advanced usage, use Letta REST API directly.
    """
    try:
        import httpx

        headers = {}
        if LETTA_API_KEY:
            headers['Authorization'] = f'Bearer {LETTA_API_KEY}'

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{LETTA_BASE_URL}/api/agents', headers=headers, timeout=10.0
            )
            response.raise_for_status()

            agents_data = response.json()

            # Format response
            agents_list = []
            for agent in agents_data.get('agents', []):
                agents_list.append(
                    {
                        'id': agent.get('id'),
                        'name': agent.get('name'),
                        'description': agent.get('description'),
                        'tools': agent.get('tools', []),
                        'created_at': agent.get('created_at'),
                    }
                )

            return JSONResponse(
                {
                    'agents': agents_list,
                    'total_count': len(agents_list),
                    'platform': 'letta',
                    'message': 'Use Letta REST API for advanced agent management',
                }
            )

    except ImportError:
        raise HTTPException(  # noqa: B904
            status_code=500,
            detail='httpx not installed. Install with: pip install httpx',
        )
    except Exception as e:
        logger.error(f'Error listing agents: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list agents: {e!s}'
        ) from e


@router.post('/chat')
async def agent_chat(message_request: ChatMessage):
    """
    Send a message to a Letta agent.

    This is a convenience endpoint. For advanced usage including streaming,
    use Letta REST API directly.

    Args:
        message_request: Chat message with optional agent name and conversation ID

    Returns:
        Agent response from Letta
    """
    try:
        import httpx

        headers = {'Content-Type': 'application/json'}
        if LETTA_API_KEY:
            headers['Authorization'] = f'Bearer {LETTA_API_KEY}'

        # Determine agent to use
        agent_name = message_request.agent_name or 'research_assistant'

        # Build request payload
        payload = {
            'message': message_request.message,
            'user_id': message_request.user_id,
        }

        if message_request.conversation_id:
            payload['thread_id'] = message_request.conversation_id

        async with httpx.AsyncClient() as client:
            # Send message to Letta
            response = await client.post(
                f'{LETTA_BASE_URL}/api/agents/{agent_name}/messages',
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()

            result = response.json()

            return JSONResponse(
                {
                    'response': result.get('message', 'No response'),
                    'agent_name': agent_name,
                    'conversation_id': result.get('thread_id'),
                    'user_id': message_request.user_id,
                    'platform': 'letta',
                }
            )

    except ImportError:
        raise HTTPException(  # noqa: B904
            status_code=500,
            detail='httpx not installed. Install with: pip install httpx',
        )
    except Exception as e:
        logger.error(f'Error in agent chat: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to process agent chat: {e!s}'
        ) from e


@router.post('/create')
async def create_agent(request: AgentCreateRequest):
    """
    Create a new Letta agent.

    This is a convenience endpoint. For advanced configuration,
    use Letta REST API directly.

    Args:
        request: Agent creation parameters

    Returns:
        Created agent details
    """
    try:
        import httpx

        headers = {'Content-Type': 'application/json'}
        if LETTA_API_KEY:
            headers['Authorization'] = f'Bearer {LETTA_API_KEY}'

        # Build agent config
        agent_config = {
            'name': request.name,
            'description': request.description or f'Agent: {request.name}',
        }

        if request.tools:
            agent_config['tools'] = request.tools

        if request.system_prompt:
            agent_config['system_prompt'] = request.system_prompt

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'{LETTA_BASE_URL}/api/agents',
                headers=headers,
                json=agent_config,
                timeout=30.0,
            )
            response.raise_for_status()

            result = response.json()

            return JSONResponse(
                {
                    'agent': result,
                    'message': 'Agent created successfully',
                    'platform': 'letta',
                }
            )

    except ImportError:
        raise HTTPException(  # noqa: B904
            status_code=500,
            detail='httpx not installed. Install with: pip install httpx',
        )
    except Exception as e:
        logger.error(f'Error creating agent: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to create agent: {e!s}'
        ) from e


@router.get('/config')
def get_agent_config():
    """
    Get Letta configuration.

    Returns sanitized configuration for agent management.
    """
    try:
        sanitized_config = {
            'letta': {
                'base_url': LETTA_BASE_URL,
                'has_api_key': bool(LETTA_API_KEY),
                'platform': 'letta',
            },
            'thoth': {
                'workspace_dir': str(config.workspace_dir),
                'pdf_dir': str(config.pdf_dir),
                'notes_dir': str(config.notes_dir),
            },
            'message': 'For advanced agent configuration, use Letta REST API directly',
            'api_docs': f'{LETTA_BASE_URL}/docs',
        }

        return JSONResponse(sanitized_config)

    except Exception as e:
        logger.error(f'Error getting config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get config: {e!s}'
        ) from e


@router.get('/info')
def agent_info():
    """
    Get information about Letta agent management.

    Returns documentation and guidance for using Letta agents.
    """
    return JSONResponse(
        {
            'platform': 'letta',
            'base_url': LETTA_BASE_URL,
            'api_docs': f'{LETTA_BASE_URL}/docs',
            'description': 'All agent management is handled by Letta platform',
            'features': [
                'Multi-agent orchestration',
                'Built-in memory management',
                'Tool calling and coordination',
                'Dynamic agent creation',
                'Conversation threading',
                'Archival memory (RAG-backed)',
                'Recall memory (entity tracking)',
            ],
            'endpoints': {
                'health': f'{LETTA_BASE_URL}/health',
                'agents': f'{LETTA_BASE_URL}/api/agents',
                'messages': f'{LETTA_BASE_URL}/api/agents/{{agent_name}}/messages',
                'docs': f'{LETTA_BASE_URL}/docs',
            },
            'recommendations': [
                'Use Letta REST API directly for advanced features',
                'These proxy endpoints are for basic convenience only',
                'Streaming responses available via Letta API',
                'See Letta docs: https://docs.letta.com/',
            ],
        }
    )
