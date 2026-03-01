"""
Agent proxy endpoints for Letta integration.

This module provides optional convenience endpoints for interacting with
Letta agents. Direct Letta REST API access is recommended for advanced usage.

All agent management is now handled by the Letta platform running on port 8283.
"""

import json
import os
import re
from pathlib import Path
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.config import config
from thoth.mcp.auth import get_current_user_paths

router = APIRouter()

LETTA_API_KEY = os.getenv('LETTA_SERVER_PASS', '')


def _get_letta_base_url() -> str:
    """Resolve the Letta server URL at request time.

    Priority order:
    1. LETTA_BASE_URL env var — explicit override (CI, custom deployments)
    2. THOTH_LETTA_URL env var — Docker-compose injection (http://letta-server:8283)
    3. config.settings.memory.letta.server_url — wizard-configured value
       (covers cloud users with https://api.letta.com and remote self-hosted)
    """
    url = (
        os.getenv('LETTA_BASE_URL')
        or os.getenv('THOTH_LETTA_URL')
        or config.settings.memory.letta.server_url
    )
    return (url or 'http://letta-server:8283').rstrip('/')


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


async def _resolve_user_agent_ids(
    request: Request, user_id: str
) -> dict[str, str | None]:
    """Resolve orchestrator/analyst agent IDs for the authenticated user."""
    service_manager = getattr(request.app.state, 'service_manager', None)
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    row = await service_manager.auth.postgres.fetchrow(
        """
        SELECT orchestrator_agent_id, analyst_agent_id
        FROM users
        WHERE id = $1 AND is_active = TRUE
        """,
        user_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='Authenticated user not found')

    return {
        'orchestrator': row['orchestrator_agent_id'],
        'analyst': row['analyst_agent_id'],
    }


@router.get('/status')
def agent_status():
    """
    Check Letta agent service status.

    Returns health status of the Letta platform.
    """
    try:
        import httpx

        # Check if Letta is accessible
        response = httpx.get(f'{_get_letta_base_url()}/health', timeout=5.0)

        if response.status_code == 200:
            return JSONResponse(
                {
                    'status': 'running',
                    'platform': 'letta',
                    'base_url': _get_letta_base_url(),
                    'message': 'Letta platform is running and accessible',
                }
            )
        else:
            return JSONResponse(
                {
                    'status': 'degraded',
                    'platform': 'letta',
                    'base_url': _get_letta_base_url(),
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
                'base_url': _get_letta_base_url(),
                'error': str(e),
                'message': 'Cannot connect to Letta platform',
            },
            status_code=503,
        )


@router.get('/list')
async def list_available_agents(
    request: Request,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    List all available Letta agents.

    This is a convenience endpoint. For advanced usage, use Letta REST API directly.
    """
    try:
        import httpx

        user_agents = await _resolve_user_agent_ids(request, _user_context.user_id)
        allowed_ids = {
            agent_id for agent_id in user_agents.values() if agent_id is not None
        }

        # User has no agents provisioned yet — skip the Letta call entirely.
        if not allowed_ids:
            return JSONResponse(
                {
                    'agents': [],
                    'total_count': 0,
                    'platform': 'letta',
                    'message': 'No agents provisioned for this user',
                }
            )

        headers = {}
        if LETTA_API_KEY:
            headers['Authorization'] = f'Bearer {LETTA_API_KEY}'

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{_get_letta_base_url()}/v1/agents/', headers=headers, timeout=10.0
            )
            response.raise_for_status()

            # Letta v1 returns a plain array, not {"agents": [...]}
            agents_data = response.json()
            if isinstance(agents_data, dict):
                agents_data = agents_data.get('agents', [])

            agents_list = []
            for agent in agents_data:
                agent_id = agent.get('id')
                if agent_id not in allowed_ids:
                    continue
                agents_list.append(
                    {
                        'id': agent_id,
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
async def agent_chat(
    request: Request,
    message_request: ChatMessage,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
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

        user_agents = await _resolve_user_agent_ids(request, user_context.user_id)
        requested_role = (message_request.agent_name or 'orchestrator').lower()
        preferred_role = 'analyst' if 'analyst' in requested_role else 'orchestrator'
        agent_id = (
            user_agents.get(preferred_role)
            or user_agents.get('orchestrator')
            or user_agents.get('analyst')
        )
        if not agent_id:
            raise HTTPException(
                status_code=400,
                detail='No Letta agent is configured for the authenticated user',
            )

        # Build request payload
        payload = {
            'message': message_request.message,
            # Always enforce authenticated user identity in multi-user mode.
            'user_id': user_context.user_id,
        }

        if message_request.conversation_id:
            payload['thread_id'] = message_request.conversation_id

        async with httpx.AsyncClient() as client:
            # Send message to Letta
            response = await client.post(
                f'{_get_letta_base_url()}/api/agents/{agent_id}/messages',
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()

            result = response.json()

            return JSONResponse(
                {
                    'response': result.get('message', 'No response'),
                    'agent_name': preferred_role,
                    'agent_id': agent_id,
                    'conversation_id': result.get('thread_id'),
                    'user_id': user_context.user_id,
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
async def create_agent(
    request: AgentCreateRequest,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
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
                f'{_get_letta_base_url()}/api/agents',
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
def get_agent_config(
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    Get Letta configuration.

    Returns sanitized configuration for agent management.
    """
    try:
        user_paths = get_current_user_paths()
        workspace_dir = user_paths.workspace_dir if user_paths else config.workspace_dir
        pdf_dir = user_paths.pdf_dir if user_paths else config.pdf_dir
        notes_dir = user_paths.notes_dir if user_paths else config.notes_dir
        sanitized_config = {
            'letta': {
                'base_url': _get_letta_base_url(),
                'has_api_key': bool(LETTA_API_KEY),
                'platform': 'letta',
            },
            'thoth': {
                'workspace_dir': str(workspace_dir),
                'pdf_dir': str(pdf_dir),
                'notes_dir': str(notes_dir),
            },
            'message': 'For advanced agent configuration, use Letta REST API directly',
            'api_docs': f'{_get_letta_base_url()}/docs',
        }

        return JSONResponse(sanitized_config)

    except Exception as e:
        logger.error(f'Error getting config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get config: {e!s}'
        ) from e


class TitleRequest(BaseModel):
    """Request body for conversation title generation."""

    message: str


class BackfillResult(BaseModel):
    """Summary returned by the backfill-titles endpoint."""

    updated: int
    skipped: int
    errors: int


# Patterns that indicate a conversation has never been given a real title.
_DEFAULT_TITLE_RE = re.compile(
    r'^(New Chat - .+|Chat [0-9a-f]{8,}|Default Conversation)$',
    re.IGNORECASE,
)


def _is_default_title(summary: str | None) -> bool:
    if not summary:
        return True
    return bool(_DEFAULT_TITLE_RE.match(summary.strip()))


async def _generate_title(message: str) -> str:
    """Call the configured LLM to produce a 3-6 word conversation title."""
    import asyncio

    from thoth.services.llm_service import LLMService

    title_model = config.settings.memory.letta.conversation_title_model or None
    llm = LLMService(config)

    prompt = (
        'Generate a short title (3 to 6 words) for a conversation that starts '
        f'with this message. Return only the title — no quotes, no punctuation at the end:\n\n{message[:500]}'
    )

    client = await asyncio.to_thread(
        llm.get_client,
        model=title_model,
        temperature=0.3,
        max_tokens=30,
    )
    response = await asyncio.to_thread(llm.invoke_with_retry, client, prompt)
    # LangChain returns an AIMessage; extract content string.
    raw = response.content if hasattr(response, 'content') else str(response)
    return raw.strip().strip('"').strip("'")


@router.post('/conversations/generate-title')
async def generate_conversation_title(
    request: TitleRequest,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    Generate a short LLM-produced title from the first message of a conversation.

    Args:
        request: Contains the user's opening message.

    Returns:
        JSON with a `title` string (3-6 words).
    """
    try:
        title = await _generate_title(request.message)
        return JSONResponse({'title': title})
    except Exception as e:
        logger.error(f'Title generation failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Title generation failed: {e!s}'
        ) from e


@router.post('/conversations/backfill-titles')
async def backfill_conversation_titles(
    http_request: Request,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    Generate titles for all conversations that still have a default or empty name.

    Fetches the user's conversations from Letta, skips any that already have a
    meaningful title, then generates and PATCHes titles for the rest.

    Returns:
        JSON summary with updated/skipped/errors counts.
    """
    import httpx

    updated = skipped = errors = 0

    try:
        user_agents = await _resolve_user_agent_ids(http_request, user_context.user_id)
        agent_id = user_agents.get('orchestrator') or user_agents.get('analyst')
        if not agent_id:
            raise HTTPException(
                status_code=400, detail='No Letta agent configured for this user'
            )

        letta_headers: dict[str, str] = {'Content-Type': 'application/json'}
        if LETTA_API_KEY:
            letta_headers['Authorization'] = f'Bearer {LETTA_API_KEY}'

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Fetch all conversations for this agent
            resp = await client.get(
                f'{_get_letta_base_url()}/v1/conversations/',
                params={'agent_id': agent_id, 'limit': 200},
                headers=letta_headers,
            )
            resp.raise_for_status()
            conversations = resp.json()

            for conv in conversations:
                conv_id = conv.get('id')
                summary = conv.get('summary') or ''

                if not _is_default_title(summary):
                    skipped += 1
                    continue

                # Fetch the first few messages to find the opening user message
                try:
                    msgs_resp = await client.get(
                        f'{_get_letta_base_url()}/v1/conversations/{conv_id}/messages',
                        params={'limit': 10, 'order': 'asc'},
                        headers=letta_headers,
                    )
                    msgs_resp.raise_for_status()
                    messages = msgs_resp.json()
                except Exception as e:
                    logger.warning(
                        f'Could not fetch messages for conversation {conv_id}: {e}'
                    )
                    errors += 1
                    continue

                # Find first user text message
                first_user_text = ''
                for msg in messages:
                    role = msg.get('role') or msg.get('message_type') or ''
                    content = msg.get('content') or msg.get('text') or ''
                    if isinstance(content, list):
                        # Multimodal: extract text parts
                        content = ' '.join(
                            part.get('text', '')
                            for part in content
                            if isinstance(part, dict)
                        )
                    if 'user' in role.lower() and content.strip():
                        first_user_text = content.strip()
                        break

                if not first_user_text:
                    skipped += 1
                    continue

                try:
                    title = await _generate_title(first_user_text)
                    patch_resp = await client.patch(
                        f'{_get_letta_base_url()}/v1/conversations/{conv_id}',
                        headers=letta_headers,
                        json={'summary': title},
                    )
                    patch_resp.raise_for_status()
                    updated += 1
                except Exception as e:
                    logger.warning(
                        f'Failed to generate/set title for conversation {conv_id}: {e}'
                    )
                    errors += 1

        return JSONResponse({'updated': updated, 'skipped': skipped, 'errors': errors})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Backfill titles failed: {e}')
        raise HTTPException(status_code=500, detail=f'Backfill failed: {e!s}') from e


def _archive_file_path() -> Path:
    """Path to the per-vault archived conversations list."""
    return config.vault_root / 'thoth' / '_thoth' / 'archived_conversations.json'


def _read_archived_ids() -> list[str]:
    """Load archived conversation IDs from disk."""
    path = _archive_file_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data.get('archived', [])
    except Exception:
        return []


def _write_archived_ids(ids: list[str]) -> None:
    """Persist archived conversation IDs to disk."""
    path = _archive_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'archived': ids}, indent=2), encoding='utf-8')


@router.get('/conversations/archived')
def list_archived_conversations(
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """Return the list of archived conversation IDs for this vault."""
    return JSONResponse({'archived': _read_archived_ids()})


@router.post('/conversations/{conv_id}/archive')
def archive_conversation(
    conv_id: str,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """Mark a conversation as archived (hidden from the main list)."""
    ids = _read_archived_ids()
    if conv_id not in ids:
        ids.append(conv_id)
        _write_archived_ids(ids)
    return JSONResponse({'archived': ids})


@router.delete('/conversations/{conv_id}/archive')
def unarchive_conversation(
    conv_id: str,
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """Restore a conversation from the archive."""
    ids = _read_archived_ids()
    ids = [i for i in ids if i != conv_id]
    _write_archived_ids(ids)
    return JSONResponse({'archived': ids})


@router.get('/info')
def agent_info(
    _user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """
    Get information about Letta agent management.

    Returns documentation and guidance for using Letta agents.
    """
    return JSONResponse(
        {
            'platform': 'letta',
            'base_url': _get_letta_base_url(),
            'api_docs': f'{_get_letta_base_url()}/docs',
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
                'health': f'{_get_letta_base_url()}/health',
                'agents': f'{_get_letta_base_url()}/api/agents',
                'messages': f'{_get_letta_base_url()}/api/agents/{{agent_name}}/messages',
                'docs': f'{_get_letta_base_url()}/docs',
            },
            'recommendations': [
                'Use Letta REST API directly for advanced features',
                'These proxy endpoints are for basic convenience only',
                'Streaming responses available via Letta API',
                'See Letta docs: https://docs.letta.com/',
            ],
        }
    )
