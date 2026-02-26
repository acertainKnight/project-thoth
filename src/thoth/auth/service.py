"""
Authentication service for user management and token-based auth.

Handles user creation, token generation, and token validation for
multi-tenant deployments.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from thoth.auth.context import UserContext
from thoth.auth.models import User

if TYPE_CHECKING:
    from pathlib import Path

    from thoth.services.postgres_service import PostgresService


class AuthService:
    """
    Service for token-based user authentication.

    Provides simple, long-lived API token auth for multi-user deployments.
    No passwords, no JWT refresh flows - just persistent API keys.

    Args:
        postgres: PostgreSQL service for database access

    Example:
        >>> auth = AuthService(postgres_service)
        >>> token = auth.generate_token()
        >>> user = await auth.create_user('alice', 'alice@example.com')
        >>> ctx = await auth.get_user_context_from_token(token)
    """

    def __init__(self, postgres: PostgresService):
        """
        Initialize auth service.

        Args:
            postgres: PostgreSQL service instance
        """
        self.postgres = postgres

    @staticmethod
    def generate_token() -> str:
        """
        Generate a secure API token.

        Returns:
            Token string in format 'thoth_<random>' (32 bytes urlsafe)

        Example:
            >>> token = AuthService.generate_token()
            >>> token.startswith('thoth_')
            True
        """
        random_part = secrets.token_urlsafe(32)
        return f'thoth_{random_part}'

    async def create_user(
        self,
        username: str,
        email: str | None = None,
        vault_path: str | None = None,
        is_admin: bool = False,
    ) -> User:
        """
        Create a new user with an API token.

        Args:
            username: Unique username
            email: Optional email address
            vault_path: Relative vault path (defaults to username)
            is_admin: Whether user should have admin privileges

        Returns:
            Created User object with token

        Raises:
            Exception: If username already exists or database error

        Example:
            >>> user = await auth.create_user('alice', 'alice@example.com')
            >>> print(user.api_token)
            'thoth_abc123...'
        """
        token = self.generate_token()
        vault_path = vault_path or username

        query = """
            INSERT INTO users (username, email, api_token, vault_path, is_admin)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, username, email, api_token, vault_path,
                      orchestrator_agent_id, analyst_agent_id,
                      is_admin, is_active, created_at, updated_at
        """

        try:
            result = await self.postgres.fetchrow(
                query, username, email, token, vault_path, is_admin
            )

            if not result:
                raise RuntimeError('Failed to create user: no result returned')

            user = User(
                id=result['id'],
                username=result['username'],
                email=result['email'],
                api_token=result['api_token'],
                vault_path=result['vault_path'],
                orchestrator_agent_id=result['orchestrator_agent_id'],
                analyst_agent_id=result['analyst_agent_id'],
                is_admin=result['is_admin'],
                is_active=result['is_active'],
                created_at=result['created_at'],
                updated_at=result['updated_at'],
            )

            logger.info(f'Created user: {username} (ID: {user.id})')
            return user

        except Exception as e:
            logger.error(f'Failed to create user {username}: {e}')
            raise

    async def get_user_by_token(self, token: str) -> User | None:
        """
        Look up user by API token.

        Args:
            token: API token to validate

        Returns:
            User object if token is valid and user is active, None otherwise

        Example:
            >>> user = await auth.get_user_by_token('thoth_abc123...')
            >>> if user:
            ...     print(f'Authenticated as {user.username}')
        """
        query = """
            SELECT id, username, email, api_token, vault_path,
                   orchestrator_agent_id, analyst_agent_id,
                   is_admin, is_active, created_at, updated_at
            FROM users
            WHERE api_token = $1 AND is_active = TRUE
        """

        try:
            result = await self.postgres.fetchrow(query, token)

            if not result:
                return None

            return User(
                id=result['id'],
                username=result['username'],
                email=result['email'],
                api_token=result['api_token'],
                vault_path=result['vault_path'],
                orchestrator_agent_id=result['orchestrator_agent_id'],
                analyst_agent_id=result['analyst_agent_id'],
                is_admin=result['is_admin'],
                is_active=result['is_active'],
                created_at=result['created_at'],
                updated_at=result['updated_at'],
            )

        except Exception as e:
            logger.error(f'Error looking up user by token: {e}')
            return None

    async def get_user_by_username(self, username: str) -> User | None:
        """
        Look up user by username.

        Args:
            username: Username to find

        Returns:
            User object if found, None otherwise
        """
        query = """
            SELECT id, username, email, api_token, vault_path,
                   orchestrator_agent_id, analyst_agent_id,
                   is_admin, is_active, created_at, updated_at
            FROM users
            WHERE username = $1
        """

        try:
            result = await self.postgres.fetchrow(query, username)

            if not result:
                return None

            return User(
                id=result['id'],
                username=result['username'],
                email=result['email'],
                api_token=result['api_token'],
                vault_path=result['vault_path'],
                orchestrator_agent_id=result['orchestrator_agent_id'],
                analyst_agent_id=result['analyst_agent_id'],
                is_admin=result['is_admin'],
                is_active=result['is_active'],
                created_at=result['created_at'],
                updated_at=result['updated_at'],
            )

        except Exception as e:
            logger.error(f'Error looking up user {username}: {e}')
            return None

    async def update_agent_ids(
        self,
        user_id: UUID,
        orchestrator_agent_id: str | None = None,
        analyst_agent_id: str | None = None,
    ) -> bool:
        """
        Update Letta agent IDs for a user.

        Called after creating Letta agents for a new user to store
        the agent IDs for future reference.

        Args:
            user_id: User's UUID
            orchestrator_agent_id: Letta orchestrator agent UUID
            analyst_agent_id: Letta analyst agent UUID

        Returns:
            True if updated successfully

        Example:
            >>> success = await auth.update_agent_ids(
            ...     user_id=UUID('...'),
            ...     orchestrator_agent_id='agent-123',
            ...     analyst_agent_id='agent-456',
            ... )
        """
        updates = []
        params = []
        param_idx = 1

        if orchestrator_agent_id is not None:
            updates.append(f'orchestrator_agent_id = ${param_idx}')
            params.append(orchestrator_agent_id)
            param_idx += 1

        if analyst_agent_id is not None:
            updates.append(f'analyst_agent_id = ${param_idx}')
            params.append(analyst_agent_id)
            param_idx += 1

        if not updates:
            return True

        updates.append('updated_at = NOW()')
        params.append(user_id)

        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
        """

        try:
            await self.postgres.execute(query, *params)
            logger.info(f'Updated agent IDs for user {user_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to update agent IDs for user {user_id}: {e}')
            return False

    async def reset_token(self, user_id: UUID) -> str:
        """
        Generate and store a new API token for a user.

        Args:
            user_id: User's UUID

        Returns:
            New API token

        Raises:
            Exception: If user not found or database error

        Example:
            >>> new_token = await auth.reset_token(user_id)
        """
        new_token = self.generate_token()

        query = """
            UPDATE users
            SET api_token = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING api_token
        """

        try:
            result = await self.postgres.fetchrow(query, new_token, user_id)
            if not result:
                raise RuntimeError(f'User {user_id} not found')

            logger.info(f'Reset API token for user {user_id}')
            return new_token

        except Exception as e:
            logger.error(f'Failed to reset token for user {user_id}: {e}')
            raise

    async def deactivate_user(self, user_id: UUID) -> bool:
        """
        Deactivate a user account.

        Args:
            user_id: User's UUID

        Returns:
            True if deactivated successfully

        Example:
            >>> success = await auth.deactivate_user(user_id)
        """
        query = """
            UPDATE users
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1
        """

        try:
            await self.postgres.execute(query, user_id)
            logger.info(f'Deactivated user {user_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to deactivate user {user_id}: {e}')
            return False

    async def get_user_context_from_token(
        self, token: str, vaults_root: Path
    ) -> UserContext | None:
        """
        Build UserContext from API token.

        Args:
            token: API token to validate
            vaults_root: Root directory containing all user vaults

        Returns:
            UserContext if token is valid, None otherwise

        Example:
            >>> ctx = await auth.get_user_context_from_token(
            ...     'thoth_abc123...', Path('/vaults')
            ... )
            >>> if ctx:
            ...     print(f'User: {ctx.username}, Vault: {ctx.vault_path}')
        """
        user = await self.get_user_by_token(token)
        if not user:
            return None

        vault_path = vaults_root / user.vault_path

        return UserContext(
            user_id=str(user.id),
            username=user.username,
            vault_path=vault_path,
            is_admin=user.is_admin,
        )
