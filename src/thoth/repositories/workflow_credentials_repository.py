"""
Workflow Credentials repository for managing encrypted authentication credentials.

This module provides secure storage and retrieval of workflow authentication
credentials using Fernet symmetric encryption.
"""

import os
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from loguru import logger

from thoth.repositories.base import BaseRepository


class WorkflowCredentialsRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing encrypted workflow credentials."""

    def __init__(self, postgres_service, encryption_key: str | None = None, **kwargs):
        """
        Initialize workflow credentials repository.

        Args:
            postgres_service: PostgreSQL service instance
            encryption_key: Base64-encoded Fernet key. If None, reads from WORKFLOW_ENCRYPTION_KEY env var
        """  # noqa: W505
        super().__init__(postgres_service, table_name='workflow_credentials', **kwargs)

        # Get or validate encryption key
        key = encryption_key or os.getenv('WORKFLOW_ENCRYPTION_KEY')
        if not key:
            raise ValueError(
                'WORKFLOW_ENCRYPTION_KEY environment variable must be set. '
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )

        try:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ValueError(f'Invalid encryption key: {e}') from e

        logger.info('WorkflowCredentialsRepository initialized with encryption')

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string."""
        return self.cipher.decrypt(ciphertext.encode()).decode()

    async def create(
        self,
        workflow_id: UUID,
        credential_type: str,
        credentials: dict[str, str],
        user_id: str | None = None,
    ) -> UUID | None:
        """
        Create encrypted credentials for a workflow.

        Args:
            workflow_id: UUID of the parent workflow
            credential_type: Type of credentials ('basic_auth', 'oauth', 'api_key', 'form')
            credentials: Dictionary of credential fields to encrypt (e.g., {'username': 'user', 'password': 'pass'})

        Returns:
            Optional[UUID]: ID of created credential record or None
        """  # noqa: W505
        try:
            user_id = self._resolve_user_id(user_id, 'create')
            # Encrypt all credential values
            encrypted_credentials = {
                key: self._encrypt(value) for key, value in credentials.items()
            }

            query = """
                INSERT INTO workflow_credentials (workflow_id, credential_type, encrypted_data, user_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """

            result = await self.postgres.fetchval(
                query, workflow_id, credential_type, encrypted_credentials, user_id
            )

            self._invalidate_cache(str(workflow_id))

            logger.debug(f'Created encrypted credentials for workflow: {workflow_id}')
            return result

        except Exception as e:
            logger.error(f'Failed to create credentials: {e}')
            return None

    async def get_by_workflow_id(
        self, workflow_id: UUID, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get decrypted credentials for a workflow.

        Args:
            workflow_id: UUID of the parent workflow

        Returns:
            Optional[dict[str, Any]]: Decrypted credentials with type or None
        """
        user_id = self._resolve_user_id(user_id, 'get_by_workflow_id')
        cache_key = self._cache_key('workflow', str(workflow_id), user_id=user_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT id, workflow_id, credential_type, encrypted_data, created_at
                FROM workflow_credentials
                WHERE workflow_id = $1
                {user_filter}
            """
            if user_id is not None:
                result = await self.postgres.fetchrow(
                    query.format(user_filter='AND user_id = $2'),
                    workflow_id,
                    user_id,
                )
            else:
                result = await self.postgres.fetchrow(
                    query.format(user_filter=''), workflow_id
                )

            if not result:
                return None

            # Decrypt credentials
            encrypted_data = result['encrypted_data']
            decrypted_credentials = {
                key: self._decrypt(value) for key, value in encrypted_data.items()
            }

            data = {
                'id': result['id'],
                'workflow_id': result['workflow_id'],
                'credential_type': result['credential_type'],
                'credentials': decrypted_credentials,
                'created_at': result['created_at'],
            }

            # Cache decrypted data (in-memory cache is secure)
            self._set_in_cache(cache_key, data, ttl=300)  # 5 minute TTL

            return data

        except Exception as e:
            logger.error(f'Failed to get credentials for workflow {workflow_id}: {e}')
            return None

    async def update(self, workflow_id: UUID, credentials: dict[str, str]) -> bool:
        """
        Update encrypted credentials for a workflow.

        Args:
            workflow_id: UUID of the parent workflow
            credentials: New credential dictionary to encrypt

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Encrypt all credential values
            encrypted_credentials = {
                key: self._encrypt(value) for key, value in credentials.items()
            }

            query = """
                UPDATE workflow_credentials
                SET encrypted_data = $1
                WHERE workflow_id = $2
            """

            await self.postgres.execute(query, encrypted_credentials, workflow_id)

            self._invalidate_cache(str(workflow_id))

            logger.debug(f'Updated credentials for workflow: {workflow_id}')
            return True

        except Exception as e:
            logger.error(
                f'Failed to update credentials for workflow {workflow_id}: {e}'
            )
            return False

    async def delete(self, workflow_id: UUID) -> bool:
        """
        Delete credentials for a workflow.

        Args:
            workflow_id: UUID of the parent workflow

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = 'DELETE FROM workflow_credentials WHERE workflow_id = $1'
            await self.postgres.execute(query, workflow_id)

            self._invalidate_cache(str(workflow_id))

            logger.info(f'Deleted credentials for workflow: {workflow_id}')
            return True

        except Exception as e:
            logger.error(
                f'Failed to delete credentials for workflow {workflow_id}: {e}'
            )
            return False

    async def exists(self, workflow_id: UUID) -> bool:
        """
        Check if credentials exist for a workflow.

        Args:
            workflow_id: UUID of the parent workflow

        Returns:
            bool: True if credentials exist, False otherwise
        """
        try:
            query = 'SELECT EXISTS(SELECT 1 FROM workflow_credentials WHERE workflow_id = $1)'
            return await self.postgres.fetchval(query, workflow_id) or False

        except Exception as e:
            logger.error(
                f'Failed to check credentials existence for workflow {workflow_id}: {e}'
            )
            return False
