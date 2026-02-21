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
from contextvars import ContextVar, Token
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from thoth.config import UserPaths
    from thoth.services.service_manager import ServiceManager

_CURRENT_MCP_USER_ID: ContextVar[str | None] = ContextVar(
    'current_mcp_user_id', default=None
)
_CURRENT_USERNAME: ContextVar[str | None] = ContextVar('current_username', default=None)
_CURRENT_VAULT_PATH: ContextVar[Path | None] = ContextVar(
    'current_vault_path', default=None
)


def set_current_user_context(
    user_id: str | None,
    username: str | None = None,
    vault_path: Path | None = None,
) -> tuple[Token, Token, Token]:
    """Set all user ContextVars for the current async context.

    Args:
        user_id: User's UUID string.
        username: Human-readable username.
        vault_path: Absolute path to the user's vault directory.

    Returns:
        Tuple of tokens for resetting all three ContextVars.
    """
    return (
        _CURRENT_MCP_USER_ID.set(user_id),
        _CURRENT_USERNAME.set(username),
        _CURRENT_VAULT_PATH.set(vault_path),
    )


def reset_current_user_context(
    tokens: tuple[Token, Token, Token],
) -> None:
    """Reset all user ContextVars using tokens from ``set_current_user_context``."""
    _CURRENT_MCP_USER_ID.reset(tokens[0])
    _CURRENT_USERNAME.reset(tokens[1])
    _CURRENT_VAULT_PATH.reset(tokens[2])


def set_current_mcp_user_id(user_id: str | None) -> Token:
    """Set the MCP user_id for the current async context."""
    return _CURRENT_MCP_USER_ID.set(user_id)


def reset_current_mcp_user_id(token: Token) -> None:
    """Reset MCP user_id context using a previous token."""
    _CURRENT_MCP_USER_ID.reset(token)


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

    context_user_id = _CURRENT_MCP_USER_ID.get()
    if context_user_id:
        return context_user_id

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


def get_current_username() -> str | None:
    """Get the username for the current async context, or None."""
    return _CURRENT_USERNAME.get()


def get_current_vault_path() -> Path | None:
    """Get the vault path for the current async context, or None."""
    return _CURRENT_VAULT_PATH.get()


def get_current_user_paths() -> UserPaths | None:
    """Resolve ``UserPaths`` for the current user using ContextVars.

    Combines the current vault_path ContextVar with
    ``Config.resolve_paths_for_vault`` to produce user-scoped paths.
    Returns None if no vault_path is set in the current context
    (e.g. single-user mode without ContextVars).

    In single-user mode, falls back to global config paths wrapped in
    a UserPaths object so callers always get the same interface.

    Returns:
        UserPaths for the current user, or None if unavailable.
    """
    from thoth.config import config

    vault_path = _CURRENT_VAULT_PATH.get()
    if vault_path:
        return config.resolve_paths_for_vault(vault_path)

    if not is_multi_user_mode():
        return config.resolve_paths_for_vault(config.vault_root)

    return None


async def resolve_mcp_user_id(
    *,
    explicit_user_id: str | None = None,
    arguments: dict[str, object] | None = None,
    service_manager: ServiceManager | None = None,
) -> str:
    """Resolve MCP user_id, including optional agent_id -> user lookup."""
    if explicit_user_id:
        return explicit_user_id

    args = arguments or {}
    agent_id = (
        args.get('agent_id')
        or args.get('letta_agent_id')
        or args.get('caller_agent_id')
    )

    if (
        is_multi_user_mode()
        and isinstance(agent_id, str)
        and agent_id
        and service_manager is not None
    ):
        try:
            row = await service_manager.auth.postgres.fetchrow(
                """
                SELECT id
                FROM users
                WHERE orchestrator_agent_id = $1 OR analyst_agent_id = $1
                LIMIT 1
                """,
                agent_id,
            )
            if row:
                return str(row['id'])
        except Exception as e:
            logger.warning(f'Failed to resolve MCP user from agent_id {agent_id}: {e}')

    return get_mcp_user_id()
