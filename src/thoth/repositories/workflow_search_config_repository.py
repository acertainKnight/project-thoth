"""
Workflow Search Config repository for managing browser workflow search configurations.

This module provides specialized methods for managing search configurations that
define how to identify and extract search results from web pages.
"""

from typing import Any
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class WorkflowSearchConfigRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing workflow search configuration records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize workflow search config repository."""
        super().__init__(
            postgres_service, table_name='workflow_search_config', **kwargs
        )

    async def create(
        self, config_data: dict[str, Any], user_id: str | None = None
    ) -> UUID | None:
        """
        Create a new workflow search configuration.

        Args:
            config_data: Dictionary containing search config data including:
                - workflow_id: UUID of the parent workflow
                - result_selector: CSS selector for result containers
                - title_selector: CSS selector for result titles
                - url_selector: CSS selector for result URLs
                - snippet_selector: Optional CSS selector for result snippets
                - pagination_config: Optional JSONB configuration for pagination
                - max_results: Maximum number of results to extract

        Returns:
            Optional[UUID]: ID of created config or None
        """
        try:
            user_id = self._resolve_user_id(user_id, 'create')
            if user_id is not None and 'user_id' not in config_data:
                config_data = {**config_data, 'user_id': user_id}
            columns = list(config_data.keys())
            placeholders = [f'${i + 1}' for i in range(len(columns))]

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """

            result = await self.postgres.fetchval(query, *config_data.values())

            # Invalidate cache for parent workflow
            if 'workflow_id' in config_data:
                self._invalidate_cache(str(config_data['workflow_id']))

            logger.debug(f'Created workflow search config: {result}')
            return result

        except Exception as e:
            logger.error(f'Failed to create workflow search config: {e}')
            return None

    async def get_by_workflow_id(
        self, workflow_id: UUID, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get search configuration for a workflow.

        Note: Each workflow should have at most one search configuration.

        Args:
            workflow_id: UUID of the parent workflow

        Returns:
            Optional[dict[str, Any]]: Search config data or None
        """
        user_id = self._resolve_user_id(user_id, 'get_by_workflow_id')
        cache_key = self._cache_key('workflow', str(workflow_id), user_id=user_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE workflow_id = $1
                {'AND user_id = $2' if user_id is not None else ''}
            """
            if user_id is not None:
                result = await self.postgres.fetchrow(query, workflow_id, user_id)
            else:
                result = await self.postgres.fetchrow(query, workflow_id)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get search config for workflow {workflow_id}: {e}')
            return None

    async def update(self, config_id: UUID, updates: dict[str, Any]) -> bool:
        """
        Update a workflow search configuration.

        Args:
            config_id: Config UUID
            updates: Dictionary of fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not updates:
                return True

            # Build SET clause
            set_clauses = [f'{col} = ${i + 2}' for i, col in enumerate(updates.keys())]
            values = [config_id] + list(updates.values())  # noqa: RUF005

            query = f"""
                UPDATE {self.table_name}
                SET {', '.join(set_clauses)}
                WHERE id = $1
                RETURNING workflow_id
            """

            workflow_id = await self.postgres.fetchval(query, *values)

            # Invalidate cache for this config and parent workflow
            self._invalidate_cache(str(config_id))
            if workflow_id:
                self._invalidate_cache(str(workflow_id))

            logger.debug(f'Updated workflow search config: {config_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to update workflow search config {config_id}: {e}')
            return False

    async def delete(self, config_id: UUID) -> bool:
        """
        Delete a workflow search configuration.

        Args:
            config_id: Config UUID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get workflow_id before deletion for cache invalidation
            workflow_id_query = (
                f'SELECT workflow_id FROM {self.table_name} WHERE id = $1'
            )
            workflow_id = await self.postgres.fetchval(workflow_id_query, config_id)

            query = f'DELETE FROM {self.table_name} WHERE id = $1'
            await self.postgres.execute(query, config_id)

            # Invalidate cache
            self._invalidate_cache(str(config_id))
            if workflow_id:
                self._invalidate_cache(str(workflow_id))

            logger.debug(f'Deleted workflow search config: {config_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to delete workflow search config {config_id}: {e}')
            return False

    async def validate_selectors(self, config_id: UUID) -> dict[str, bool]:
        """
        Validate that all required selectors are present in the configuration.

        Args:
            config_id: Config UUID

        Returns:
            dict[str, bool]: Dictionary with validation results for each selector
        """
        try:
            query = f"""
                SELECT
                    result_selector,
                    title_selector,
                    url_selector,
                    snippet_selector
                FROM {self.table_name}
                WHERE id = $1
            """
            result = await self.postgres.fetchrow(query, config_id)

            if not result:
                return {}

            validation = {
                'result_selector': bool(result['result_selector']),
                'title_selector': bool(result['title_selector']),
                'url_selector': bool(result['url_selector']),
                'snippet_selector': bool(result['snippet_selector']),
            }

            validation['is_valid'] = (
                validation['result_selector']
                and validation['title_selector']
                and validation['url_selector']
            )

            return validation

        except Exception as e:
            logger.error(f'Failed to validate selectors for config {config_id}: {e}')
            return {}

    async def get_all_configs_with_pagination(self) -> list[dict[str, Any]]:
        """
        Get all search configurations that have pagination configured.

        Returns:
            list[dict[str, Any]]: List of configs with pagination
        """
        try:
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE pagination_config IS NOT NULL
                ORDER BY created_at DESC
            """
            results = await self.postgres.fetch(query)
            return [dict(row) for row in results]

        except Exception as e:  # noqa: F841
            logger.error('Failed to get configs with pagination: {e}')
            return []

    async def update_selector(
        self, config_id: UUID, selector_name: str, selector_value: str
    ) -> bool:
        """
        Update a specific selector in the configuration.

        Args:
            config_id: Config UUID
            selector_name: Name of the selector field to update
            selector_value: New selector value

        Returns:
            bool: True if successful, False otherwise
        """
        valid_selectors = [
            'result_selector',
            'title_selector',
            'url_selector',
            'snippet_selector',
        ]

        if selector_name not in valid_selectors:
            logger.error(f'Invalid selector name: {selector_name}')
            return False

        return await self.update(config_id, {selector_name: selector_value})
