"""
Workflow Actions repository for managing browser workflow action steps.

This module provides specialized methods for managing workflow action sequences,
step ordering, and action configuration for browser automation workflows.
"""

from typing import Any, Optional
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class WorkflowActionsRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing workflow action step records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize workflow actions repository."""
        super().__init__(postgres_service, table_name='workflow_actions', **kwargs)

    async def create(self, action_data: dict[str, Any]) -> Optional[UUID]:  # noqa: UP007
        """
        Create a new workflow action step.

        Args:
            action_data: Dictionary containing action step data including:
                - workflow_id: UUID of the parent workflow
                - step_number: Integer position in workflow sequence
                - action_type: Type of action (e.g., 'navigate', 'click', 'extract')
                - selector: Optional CSS selector for action target
                - action_config: JSONB configuration for the action

        Returns:
            Optional[UUID]: ID of created action or None
        """
        try:
            columns = list(action_data.keys())
            placeholders = [f'${i + 1}' for i in range(len(columns))]

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """

            result = await self.postgres.fetchval(query, *action_data.values())

            # Invalidate cache for parent workflow
            if 'workflow_id' in action_data:
                self._invalidate_cache(str(action_data['workflow_id']))

            logger.debug(f'Created workflow action: {result}')
            return result

        except Exception as e:
            logger.error(f'Failed to create workflow action: {e}')
            return None

    async def get_by_workflow_id(self, workflow_id: UUID) -> list[dict[str, Any]]:
        """
        Get all actions for a workflow, ordered by step number.

        Args:
            workflow_id: UUID of the parent workflow

        Returns:
            list[dict[str, Any]]: List of action steps ordered by step_number
        """
        cache_key = self._cache_key('workflow', str(workflow_id))
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM workflow_actions
                WHERE workflow_id = $1
                ORDER BY step_number ASC
            """
            results = await self.postgres.fetch(query, workflow_id)
            actions = [dict(row) for row in results]

            self._set_in_cache(cache_key, actions)
            return actions

        except Exception as e:
            logger.error(f'Failed to get actions for workflow {workflow_id}: {e}')
            return []

    async def get_by_step_number(
        self, workflow_id: UUID, step_number: int
    ) -> Optional[dict[str, Any]]:  # noqa: UP007
        """
        Get a specific action step by its step number.

        Args:
            workflow_id: UUID of the parent workflow
            step_number: Step number in the sequence

        Returns:
            Optional[dict[str, Any]]: Action step data or None
        """
        cache_key = self._cache_key('workflow', str(workflow_id), 'step', step_number)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM workflow_actions
                WHERE workflow_id = $1 AND step_number = $2
            """
            result = await self.postgres.fetchrow(query, workflow_id, step_number)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(
                f'Failed to get action step {step_number} for workflow {workflow_id}: {e}'
            )
            return None

    async def update(self, action_id: UUID, updates: dict[str, Any]) -> bool:
        """
        Update a workflow action step.

        Args:
            action_id: Action UUID
            updates: Dictionary of fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not updates:
                return True

            # Build SET clause
            set_clauses = [f'{col} = ${i + 2}' for i, col in enumerate(updates.keys())]
            values = [action_id] + list(updates.values())  # noqa: RUF005

            query = f"""
                UPDATE {self.table_name}
                SET {', '.join(set_clauses)}
                WHERE id = $1
                RETURNING workflow_id
            """

            workflow_id = await self.postgres.fetchval(query, *values)

            # Invalidate cache for this action and parent workflow
            self._invalidate_cache(str(action_id))
            if workflow_id:
                self._invalidate_cache(str(workflow_id))

            logger.debug(f'Updated workflow action: {action_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to update workflow action {action_id}: {e}')
            return False

    async def delete(self, action_id: UUID) -> bool:
        """
        Delete a workflow action step.

        Args:
            action_id: Action UUID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get workflow_id before deletion for cache invalidation
            workflow_id_query = 'SELECT workflow_id FROM workflow_actions WHERE id = $1'
            workflow_id = await self.postgres.fetchval(workflow_id_query, action_id)

            query = f'DELETE FROM {self.table_name} WHERE id = $1'
            await self.postgres.execute(query, action_id)

            # Invalidate cache
            self._invalidate_cache(str(action_id))
            if workflow_id:
                self._invalidate_cache(str(workflow_id))

            logger.debug(f'Deleted workflow action: {action_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to delete workflow action {action_id}: {e}')
            return False

    async def reorder_steps(self, workflow_id: UUID, new_order: list[UUID]) -> bool:
        """
        Reorder workflow action steps by updating their step numbers.

        This method is useful for workflow editing and reorganization.

        Args:
            workflow_id: UUID of the parent workflow
            new_order: List of action UUIDs in desired order

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use a transaction to ensure atomicity
            async with self.postgres.transaction():
                for idx, action_id in enumerate(new_order, start=1):
                    query = """
                        UPDATE workflow_actions
                        SET step_number = $1
                        WHERE id = $2 AND workflow_id = $3
                    """
                    await self.postgres.execute(query, idx, action_id, workflow_id)

            # Invalidate cache for the workflow
            self._invalidate_cache(str(workflow_id))

            logger.debug(f'Reordered {len(new_order)} steps for workflow {workflow_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to reorder steps for workflow {workflow_id}: {e}')
            return False

    async def get_step_count(self, workflow_id: UUID) -> int:
        """
        Get the total number of steps in a workflow.

        Args:
            workflow_id: UUID of the parent workflow

        Returns:
            int: Number of action steps
        """
        try:
            query = """
                SELECT COUNT(*) FROM workflow_actions
                WHERE workflow_id = $1
            """
            return await self.postgres.fetchval(query, workflow_id) or 0

        except Exception as e:
            logger.error(f'Failed to count steps for workflow {workflow_id}: {e}')
            return 0

    async def get_actions_by_type(
        self, workflow_id: UUID, action_type: str
    ) -> list[dict[str, Any]]:
        """
        Get all actions of a specific type within a workflow.

        Args:
            workflow_id: UUID of the parent workflow
            action_type: Type of action to filter by

        Returns:
            list[dict[str, Any]]: List of matching action steps
        """
        try:
            query = """
                SELECT * FROM workflow_actions
                WHERE workflow_id = $1 AND action_type = $2
                ORDER BY step_number ASC
            """
            results = await self.postgres.fetch(query, workflow_id, action_type)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(
                f'Failed to get actions of type {action_type} for workflow {workflow_id}: {e}'
            )
            return []
