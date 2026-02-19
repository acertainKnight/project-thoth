"""
MCP server user context resolution for multi-tenant tool calls.

Letta agents call MCP tools server-to-server, so traditional request-level
Bearer token auth doesn't apply. Instead, tools that need to scope data to a
user can call get_mcp_user_id() which resolves the calling user via:

1. An explicit user_id argument passed by the tool caller (highest priority)
2. The THOTH_MCP_USER_ID environment variable (set per-process in single-user)
3. 'default_user' fallback (single-user mode / backward compat)

In multi-user mode, per-user Letta agents are named thoth_main_orchestrator_{username}.
The agent_id can be used to look up the user if needed for stricter validation.
"""

from __future__ import annotations

import os

from loguru import logger


def get_mcp_user_id(explicit_user_id: str | None = None) -> str:
    """
    Resolve the user_id for an MCP tool call.

    Priority order:
    1. Explicit user_id argument (passed by the tool caller)
    2. THOTH_MCP_USER_ID environment variable (process-level override)
    3. 'default_user' fallback for single-user / backward compat

    Args:
        explicit_user_id: Optional user_id explicitly passed to the tool

    Returns:
        Resolved user_id string

    Example:
        >>> user_id = get_mcp_user_id(explicit_user_id='alice-uuid')
        >>> user_id
        'alice-uuid'
        >>> # In single-user mode with no args:
        >>> get_mcp_user_id()
        'default_user'
    """
    if explicit_user_id:
        return explicit_user_id

    env_user_id = os.getenv('THOTH_MCP_USER_ID')
    if env_user_id:
        logger.debug(f'MCP tool using user_id from THOTH_MCP_USER_ID: {env_user_id}')
        return env_user_id

    return 'default_user'


def is_multi_user_mode() -> bool:
    """
    Check if the server is running in multi-user mode.

    Returns:
        True if THOTH_MULTI_USER=true
    """
    return os.getenv('THOTH_MULTI_USER', 'false').lower() == 'true'
