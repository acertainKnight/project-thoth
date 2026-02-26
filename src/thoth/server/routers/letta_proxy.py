"""
Authenticated proxy for Letta API calls.

The Obsidian plugin needs access to Letta's conversation and messaging APIs,
but Letta has no per-user authentication — it accepts any request. Routing all
plugin calls through this proxy enforces the Thoth auth layer and validates that
each user can only touch their own agents.
"""

import os
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from loguru import logger

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context

router = APIRouter()

LETTA_BASE_URL = os.getenv('LETTA_BASE_URL', 'http://letta-server:8283')
LETTA_API_KEY = os.getenv('LETTA_SERVER_PASS', '')

# Paths that contain an agent_id segment we need to validate.
# Matches /v1/agents/{agent_id} and /v1/agents/{agent_id}/anything
_AGENT_PATH_RE = re.compile(r'^agents/([^/]+)')


async def _get_user_agent_ids(request: Request, user_id: str) -> set[str]:
    """Return the set of Letta agent IDs owned by this user."""
    service_manager = getattr(request.app.state, 'service_manager', None)
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialised')

    row = await service_manager.auth.postgres.fetchrow(
        """
        SELECT orchestrator_agent_id, analyst_agent_id
        FROM users
        WHERE id = $1 AND is_active = TRUE
        """,
        user_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='User not found')

    return {
        agent_id
        for agent_id in (row['orchestrator_agent_id'], row['analyst_agent_id'])
        if agent_id is not None
    }


def _letta_headers() -> dict[str, str]:
    headers = {}
    if LETTA_API_KEY:
        headers['Authorization'] = f'Bearer {LETTA_API_KEY}'
    return headers


@router.api_route('/v1/{path:path}', methods=['GET', 'POST', 'PATCH', 'DELETE', 'PUT'])
async def letta_proxy(
    request: Request,
    path: str,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> Response:
    """
    Forward a Letta v1 API call on behalf of the authenticated user.

    Validates that any agent_id in the query string or URL path belongs to
    the requesting user before forwarding.

    Args:
        request: Incoming HTTP request (body and params forwarded as-is).
        path: The Letta v1 path to forward (e.g. conversations/abc123/messages).
        user_context: Injected auth context — enforces that a valid token is present.

    Returns:
        Letta's response, streamed back to the caller.
    """
    allowed_ids = await _get_user_agent_ids(request, user_context.user_id)

    # Validate agent_id in query (e.g. ?agent_id=... on conversation list/create).
    agent_id_param = request.query_params.get('agent_id')
    if agent_id_param and agent_id_param not in allowed_ids:
        raise HTTPException(
            status_code=403,
            detail='agent_id does not belong to the authenticated user',
        )

    # Validate agent_id embedded in path (e.g. /v1/agents/{agent_id}/messages).
    match = _AGENT_PATH_RE.match(path)
    if match:
        path_agent_id = match.group(1)
        # Some paths use generic terms like "search" — only block real-looking IDs.
        if path_agent_id.startswith('agent-') and path_agent_id not in allowed_ids:
            raise HTTPException(
                status_code=403,
                detail='agent in path does not belong to the authenticated user',
            )

    target_url = f'{LETTA_BASE_URL}/v1/{path}'
    query_string = request.url.query
    if query_string:
        target_url = f'{target_url}?{query_string}'

    headers = _letta_headers()
    # Forward content-type if present.
    if content_type := request.headers.get('content-type'):
        headers['content-type'] = content_type

    body = await request.body()

    try:
        async with httpx.AsyncClient() as client:
            letta_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body or None,
                timeout=120.0,
            )

        # Stream the response back with the original status and content-type.
        return Response(
            content=letta_response.content,
            status_code=letta_response.status_code,
            headers={
                'content-type': letta_response.headers.get(
                    'content-type', 'application/json'
                ),
            },
        )

    except httpx.TimeoutException:
        logger.warning(f'Letta proxy timeout: {request.method} /v1/{path}')
        raise HTTPException(status_code=504, detail='Letta request timed out') from None
    except Exception as e:
        logger.error(f'Letta proxy error: {request.method} /v1/{path}: {e}')
        raise HTTPException(
            status_code=502, detail=f'Letta request failed: {e!s}'
        ) from e
