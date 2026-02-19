"""
Authentication API endpoints.

Provides registration and user information endpoints for multi-user setups.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from thoth.auth.dependencies import get_user_context
from thoth.auth.models import UserCreate, UserInfo, UserResponse
from thoth.server.dependencies import get_service_manager

if TYPE_CHECKING:
    from thoth.auth.context import UserContext
    from thoth.services.service_manager import ServiceManager

router = APIRouter(prefix='/auth', tags=['authentication'])


def _self_registration_allowed() -> bool:
    """
    Check if self-registration is enabled.

    Returns:
        True if THOTH_ALLOW_REGISTRATION is 'true'
    """
    return os.getenv('THOTH_ALLOW_REGISTRATION', 'false').lower() == 'true'


@router.post('/register', response_model=UserResponse)
async def register(
    user_create: UserCreate,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> UserResponse:
    """
    Register a new user account.

    Creates a user with an API token, provisions their vault directory,
    and initializes their Letta agents.

    Args:
        user_create: Username and optional email
        service_manager: Service manager dependency

    Returns:
        UserResponse with user_id, username, and api_token

    Raises:
        HTTPException: 403 if self-registration disabled
        HTTPException: 409 if username already exists
        HTTPException: 500 if provisioning fails

    Example:
        >>> POST / auth / register
        >>> {'username': 'alice', 'email': 'alice@example.com'}
        >>> Response: {'user_id': '...', 'username': 'alice', 'api_token': 'thoth_...'}
    """
    if not _self_registration_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Self-registration is disabled. Contact admin for access.',
        )

    auth_service = service_manager.auth

    existing = await auth_service.get_user_by_username(user_create.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Username {user_create.username} already exists',
        )

    try:
        user = await auth_service.create_user(
            username=user_create.username, email=user_create.email
        )

        vaults_root = Path(os.getenv('THOTH_VAULTS_ROOT', '/vaults'))
        vault_provisioner = service_manager.vault_provisioner

        await vault_provisioner.provision_vault(user.username, vaults_root)
        logger.info(f'Provisioned vault for user {user.username}')

        if hasattr(service_manager, 'agent_initialization'):
            from thoth.auth.context import UserContext

            user_context = UserContext(
                user_id=str(user.id),
                username=user.username,
                vault_path=vaults_root / user.vault_path,
                is_admin=user.is_admin,
            )

            agent_ids = (
                await service_manager.agent_initialization.initialize_agents_for_user(
                    user_context
                )
            )

            if agent_ids:
                await auth_service.update_agent_ids(
                    user.id,
                    orchestrator_agent_id=agent_ids.get('orchestrator'),
                    analyst_agent_id=agent_ids.get('analyst'),
                )

        return UserResponse(
            user_id=str(user.id), username=user.username, api_token=user.api_token
        )

    except Exception as e:
        logger.error(f'Failed to register user {user_create.username}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='User registration failed',
        ) from e


@router.get('/me', response_model=UserInfo)
async def get_current_user_info(
    user_context: UserContext = Depends(get_user_context),
    service_manager: ServiceManager = Depends(get_service_manager),
) -> UserInfo:
    """
    Get current authenticated user's information.

    Fetches full user record from database, including Letta agent IDs
    needed by the Obsidian plugin for agent resolution.

    Args:
        user_context: Injected user context from token
        service_manager: Service manager dependency

    Returns:
        UserInfo with public user data and agent IDs

    Example:
        >>> GET / auth / me
        >>> Headers: Authorization: Bearer thoth_abc123...
        >>> Response: {"id": "...", "username": "alice", ...}
    """
    auth_service = service_manager.auth
    user = await auth_service.get_user_by_username(user_context.username)

    if user:
        return UserInfo(
            id=str(user.id),
            username=user.username,
            email=user.email,
            vault_path=str(user_context.vault_path),
            orchestrator_agent_id=user.orchestrator_agent_id,
            analyst_agent_id=user.analyst_agent_id,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    return UserInfo(
        id=user_context.user_id,
        username=user_context.username,
        vault_path=str(user_context.vault_path),
        is_admin=user_context.is_admin,
        is_active=True,
    )
