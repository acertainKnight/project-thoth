"""
Authenticated proxy for Letta API calls.

The Obsidian plugin needs access to Letta's conversation and messaging APIs,
but Letta has no per-user authentication — it accepts any request. Routing all
plugin calls through this proxy enforces the Thoth auth layer and validates that
each user can only touch their own agents.

When a POST to conversations/*/messages is intercepted, the proxy also injects
skill context into the message stream: full SKILL.md content on the
[skill-tools-ready] follow-up, and a compact reminder on every other turn.
This mirrors how Letta Code delivers skill instructions and avoids relying on
agents to reliably read their own memory blocks.
"""

import json
import os
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from loguru import logger

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.config import config

router = APIRouter()

LETTA_API_KEY = os.getenv('LETTA_SERVER_PASS', '')

# Prefix the Obsidian plugin sends after a skill is loaded/unloaded.
_SKILL_READY_PREFIX = '[skill-tools-ready]'

# Number of human messages after which an idle skill is auto-unloaded.
_AUTO_UNLOAD_AFTER = 50

# Matches /v1/conversations/{id}/messages (no trailing path segments).
_CONV_MSG_RE = re.compile(r'^conversations/([^/]+)/messages$')

# Paths that contain an agent_id segment we need to validate.
# Matches /v1/agents/{agent_id} and /v1/agents/{agent_id}/anything
_AGENT_PATH_RE = re.compile(r'^agents/([^/]+)')


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


async def _get_orchestrator_agent_id(request: Request, user_id: str) -> str | None:
    """Return the user's orchestrator agent ID from the DB."""
    service_manager = getattr(request.app.state, 'service_manager', None)
    if service_manager is None:
        return None

    row = await service_manager.auth.postgres.fetchrow(
        'SELECT orchestrator_agent_id FROM users WHERE id = $1 AND is_active = TRUE',
        user_id,
    )
    return row['orchestrator_agent_id'] if row else None


def _letta_headers() -> dict[str, str]:
    headers = {}
    if LETTA_API_KEY:
        headers['Authorization'] = f'Bearer {LETTA_API_KEY}'
    return headers


def _find_skill_path(skill_id: str, vault_path: Path) -> Path | None:
    """Find the SKILL.md for a given skill_id, checking vault then bundled.

    Args:
        skill_id: Skill directory name (e.g. 'github-issue-tracking').
        vault_path: Absolute vault root path for this user.

    Returns:
        Path to SKILL.md, or None if not found.
    """
    try:
        user_paths = config.resolve_paths_for_vault(vault_path)
        vault_skill = user_paths.workspace_dir / 'skills' / skill_id / 'SKILL.md'
        if vault_skill.exists():
            return vault_skill
    except Exception:
        pass

    # Fall back to bundled skills shipped with Thoth.
    # letta_proxy.py is at src/thoth/server/routers/, so .skills is 3 dirs up.
    bundled = Path(__file__).parent.parent.parent / '.skills' / skill_id / 'SKILL.md'
    if bundled.exists():
        return bundled

    return None


def _build_skill_reminder(skill_id: str, content: str) -> str:
    """Build a compact one-line reminder from skill YAML frontmatter.

    Args:
        skill_id: Skill identifier used as fallback name.
        content: Full SKILL.md content.

    Returns:
        str: Compact reminder for system message injection.
    """
    import yaml

    metadata: dict = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1].strip()) or {}
            except Exception:
                pass

    name = metadata.get('name', skill_id)
    description = metadata.get('description', '')
    tools = metadata.get('tools', [])
    tools_str = ', '.join(tools) if tools else 'no extra tools'

    reminder = f'[Skill active: {name}]'
    if description:
        reminder += f' {description}'
    reminder += f' | Tools: {tools_str}'
    return reminder


async def _inject_skill_context(
    request: Request,
    user_id: str,
    vault_path: Path,
    body_bytes: bytes,
) -> bytes:
    """Rewrite a conversation message body to include skill context.

    For [skill-tools-ready] messages: injects the full SKILL.md as a system
    message so the agent sees it directly in the conversation stream.

    For regular messages: injects a compact per-skill reminder so the agent
    stays aware of loaded skills without reading memory blocks.

    Also tracks message_count per skill and auto-unloads stale skills (> 50
    messages) by removing them from the DB and injecting a notification.

    Args:
        request: Incoming request (for DB access).
        user_id: Authenticated user ID.
        vault_path: Resolved vault root for finding skill files.
        body_bytes: Raw request body JSON bytes.

    Returns:
        Rewritten body bytes, or the original bytes if injection is skipped.
    """
    try:
        payload = json.loads(body_bytes)
    except Exception:
        return body_bytes

    # We only modify string inputs; skip multimodal (array) inputs.
    user_input = payload.get('input')
    if not isinstance(user_input, str):
        return body_bytes

    service_manager = getattr(request.app.state, 'service_manager', None)
    if service_manager is None:
        return body_bytes

    postgres = service_manager.auth.postgres

    # Resolve the user's orchestrator agent ID.
    row = await postgres.fetchrow(
        'SELECT orchestrator_agent_id FROM users WHERE id = $1 AND is_active = TRUE',
        user_id,
    )
    if not row or not row['orchestrator_agent_id']:
        return body_bytes

    agent_id = row['orchestrator_agent_id']

    # Fetch currently loaded skills (with message counts).
    skill_rows = await postgres.fetch(
        'SELECT skill_id, message_count FROM agent_loaded_skills '
        'WHERE agent_id = $1 ORDER BY loaded_at',
        agent_id,
    )
    if not skill_rows:
        return body_bytes

    is_skill_ready_msg = user_input.startswith(_SKILL_READY_PREFIX)
    system_messages: list[dict] = []
    skills_to_auto_unload: list[str] = []

    for row in skill_rows:
        skill_id = row['skill_id']
        msg_count = row['message_count']

        skill_path = _find_skill_path(skill_id, vault_path)
        if not skill_path:
            logger.warning(f'Skill file not found for injection: {skill_id}')
            continue

        try:
            skill_content = skill_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f'Could not read skill content for {skill_id}: {e}')
            continue

        if is_skill_ready_msg:
            # Full skill content injection -- agent sees the SKILL.md directly.
            system_messages.append(
                {
                    'role': 'system',
                    'content': (
                        f'Skill instructions for {skill_id} (follow these for this task):\n\n'
                        f'{skill_content}'
                    ),
                }
            )
        else:
            # Check for auto-unload before building reminder.
            if msg_count >= _AUTO_UNLOAD_AFTER:
                skills_to_auto_unload.append(skill_id)
                system_messages.append(
                    {
                        'role': 'system',
                        'content': (
                            f'[Skill auto-unloaded: {skill_id}] This skill was inactive for '
                            f'{_AUTO_UNLOAD_AFTER}+ messages and has been unloaded. '
                            f'Use load_skill to reload it if needed.'
                        ),
                    }
                )
            else:
                reminder = _build_skill_reminder(skill_id, skill_content)
                system_messages.append({'role': 'system', 'content': reminder})

    # Auto-unload stale skills from DB (tools stay attached until next restart).
    for skill_id in skills_to_auto_unload:
        try:
            await postgres.execute(
                'DELETE FROM agent_loaded_skills WHERE agent_id = $1 AND skill_id = $2',
                agent_id,
                skill_id,
            )
            logger.info(
                f'Auto-unloaded stale skill {skill_id!r} '
                f'from agent {agent_id[:8]} after {_AUTO_UNLOAD_AFTER} messages'
            )
        except Exception as e:
            logger.warning(f'Could not auto-unload skill {skill_id}: {e}')

    # Increment message_count for skills that are staying loaded.
    if not is_skill_ready_msg:
        staying_loaded = [
            r['skill_id']
            for r in skill_rows
            if r['skill_id'] not in skills_to_auto_unload
        ]
        if staying_loaded:
            try:
                await postgres.executemany(
                    'UPDATE agent_loaded_skills SET message_count = message_count + 1 '
                    'WHERE agent_id = $1 AND skill_id = $2',
                    [(agent_id, sid) for sid in staying_loaded],
                )
            except Exception as e:
                logger.warning(f'Could not increment skill message counts: {e}')

    if not system_messages:
        return body_bytes

    # Convert to multi-message format: system injections + user message.
    new_payload = {k: v for k, v in payload.items() if k != 'input'}
    new_payload['messages'] = [
        *system_messages,
        {'role': 'user', 'content': user_input},
    ]

    return json.dumps(new_payload).encode()


@router.api_route('/v1/{path:path}', methods=['GET', 'POST', 'PATCH', 'DELETE', 'PUT'])
async def letta_proxy(
    request: Request,
    path: str,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> Response:
    """
    Forward a Letta v1 API call on behalf of the authenticated user.

    Validates that any agent_id in the query string or URL path belongs to
    the requesting user before forwarding. For conversation message POSTs,
    injects skill context (full content or compact reminder) as system messages.

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

    target_url = f'{_get_letta_base_url()}/v1/{path}'
    query_string = request.url.query
    if query_string:
        target_url = f'{target_url}?{query_string}'

    headers = _letta_headers()
    # Forward content-type if present.
    if content_type := request.headers.get('content-type'):
        headers['content-type'] = content_type

    body = await request.body()

    # Check if the client is expecting an SSE stream so we can relay
    # chunks as they arrive rather than buffering the full response.
    wants_stream = False
    if body:
        try:
            payload = json.loads(body)
            wants_stream = payload.get('streaming', False)
        except Exception:
            pass

    # Inject skill context for conversation message POSTs.
    if request.method == 'POST' and _CONV_MSG_RE.match(path) and body:
        try:
            body = await _inject_skill_context(
                request,
                user_context.user_id,
                user_context.vault_path,
                body,
            )
        except Exception as e:
            # Never let injection errors break the actual message delivery.
            logger.warning(f'Skill injection failed for {path}: {e}')

    try:
        if wants_stream:
            # SSE / streaming path: relay chunks to the client in real time
            # so the plugin sees reasoning pills and token deltas immediately.
            client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0))
            upstream = await client.send(
                client.build_request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body or None,
                ),
                stream=True,
            )

            async def _relay():
                try:
                    async for chunk in upstream.aiter_bytes():
                        yield chunk
                finally:
                    await upstream.aclose()
                    await client.aclose()

            return StreamingResponse(
                _relay(),
                status_code=upstream.status_code,
                headers={
                    'content-type': upstream.headers.get(
                        'content-type', 'text/event-stream'
                    ),
                    'cache-control': 'no-cache',
                    'x-accel-buffering': 'no',
                },
            )

        # Non-streaming path: buffer and forward as before.
        async with httpx.AsyncClient() as client:
            letta_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body or None,
                timeout=120.0,
            )

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
