"""
Workflow Executions repository for managing browser workflow execution tracking.

This module provides specialized methods for tracking workflow executions,
their status, results, and performance metrics over time.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class WorkflowExecutionsRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing workflow execution records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize workflow executions repository."""
        super().__init__(postgres_service, table_name='workflow_executions', **kwargs)

    async def create(
        self, execution_data: dict[str, Any], user_id: str | None = None
    ) -> UUID | None:
        """
        Create a new workflow execution record.

        Args:
            execution_data: Dictionary containing execution data including:
                - workflow_id: UUID of the workflow being executed
                - status: Execution status (e.g., 'running', 'completed', 'failed')
                - started_at: Timestamp when execution started
                - execution_config: Optional JSONB configuration used for execution
                - user_id: Optional UUID of user who triggered execution

        Returns:
            Optional[UUID]: ID of created execution or None
        """
        try:
            user_id = self._resolve_user_id(user_id, 'create')
            import json as _json

            # Set default started_at if not provided
            if 'started_at' not in execution_data:
                execution_data['started_at'] = datetime.now()

            # Set default status if not provided
            if 'status' not in execution_data:
                execution_data['status'] = 'running'
            if user_id is not None and 'user_id' not in execution_data:
                execution_data['user_id'] = user_id

            # asyncpg requires JSONB values as JSON strings, not raw dicts
            serialized = {}
            for k, v in execution_data.items():
                if isinstance(v, dict) or isinstance(v, list):
                    serialized[k] = _json.dumps(v)
                else:
                    serialized[k] = v

            columns = list(serialized.keys())
            placeholders = [f'${i + 1}' for i in range(len(columns))]

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """  # nosec B608  # table_name is set in __init__, not user input

            result = await self.postgres.fetchval(query, *serialized.values())

            # Invalidate cache for parent workflow
            if 'workflow_id' in execution_data:
                self._invalidate_cache(str(execution_data['workflow_id']))

            logger.debug(f'Created workflow execution: {result}')
            return result

        except Exception as e:
            logger.error(f'Failed to create workflow execution: {e}')
            return None

    async def get_by_id(
        self, execution_id: UUID, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get a workflow execution by ID.

        Args:
            execution_id: Execution UUID

        Returns:
            Optional[dict[str, Any]]: Execution data or None
        """
        user_id = self._resolve_user_id(user_id, 'get_by_id')
        cache_key = self._cache_key('id', str(execution_id), user_id=user_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if user_id is not None:
                query = (
                    f'SELECT * FROM {self.table_name} WHERE id = $1 AND user_id = $2'  # nosec B608
                )
                result = await self.postgres.fetchrow(query, execution_id, user_id)
            else:
                query = f'SELECT * FROM {self.table_name} WHERE id = $1'  # nosec B608
                result = await self.postgres.fetchrow(query, execution_id)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get execution {execution_id}: {e}')
            return None

    async def get_by_workflow_id(
        self, workflow_id: UUID, limit: int = 10, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get recent executions for a workflow.

        Args:
            workflow_id: UUID of the workflow
            limit: Maximum number of executions to return (default: 10)

        Returns:
            list[dict[str, Any]]: List of execution records ordered by started_at DESC
        """
        user_id = self._resolve_user_id(user_id, 'get_by_workflow_id')
        cache_key = self._cache_key(
            'workflow', str(workflow_id), f'limit_{limit}', user_id=user_id
        )
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM workflow_executions
                WHERE workflow_id = $1
                {user_filter}
                ORDER BY started_at DESC
                LIMIT $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $3'),
                    workflow_id,
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''),
                    workflow_id,
                    limit,
                )
            executions = [dict(row) for row in results]

            self._set_in_cache(cache_key, executions)
            return executions

        except Exception as e:
            logger.error(f'Failed to get executions for workflow {workflow_id}: {e}')
            return []

    async def get_recent_executions(
        self, workflow_id: UUID, hours: int = 24, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get executions within a recent time window.

        Args:
            workflow_id: UUID of the workflow
            hours: Number of hours to look back (default: 24)

        Returns:
            list[dict[str, Any]]: List of recent execution records
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_recent_executions')
            since = datetime.now() - timedelta(hours=hours)

            if user_id is not None:
                query = """
                    SELECT * FROM workflow_executions
                    WHERE workflow_id = $1 AND started_at >= $2 AND user_id = $3
                    ORDER BY started_at DESC
                """
                results = await self.postgres.fetch(query, workflow_id, since, user_id)
            else:
                query = """
                    SELECT * FROM workflow_executions
                    WHERE workflow_id = $1 AND started_at >= $2
                    ORDER BY started_at DESC
                """
                results = await self.postgres.fetch(query, workflow_id, since)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(
                f'Failed to get recent executions for workflow {workflow_id}: {e}'
            )
            return []

    async def update_status(
        self,
        execution_id: UUID,
        status: str,
        error_message: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """
        Update the status of a workflow execution.

        Args:
            execution_id: Execution UUID
            status: New status (e.g., 'completed', 'failed', 'cancelled')
            error_message: Optional error message if status is 'failed'

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user_id = self._resolve_user_id(user_id, 'update_status')
            updates = {'status': status}

            # Set completed_at timestamp for terminal states
            if status in ('completed', 'failed', 'cancelled'):
                updates['completed_at'] = datetime.now()

            # Add error message if provided
            if error_message:
                updates['error_message'] = error_message

            # Build SET clause
            set_clauses = [f'{col} = ${i + 2}' for i, col in enumerate(updates.keys())]
            values = [execution_id] + list(updates.values())  # noqa: RUF005

            if user_id is not None:
                query = f"""
                    UPDATE {self.table_name}
                    SET {', '.join(set_clauses)}
                    WHERE id = $1 AND user_id = ${len(values) + 1}
                    RETURNING workflow_id
                """  # nosec B608
                values.append(user_id)
            else:
                query = f"""
                    UPDATE {self.table_name}
                    SET {', '.join(set_clauses)}
                    WHERE id = $1
                    RETURNING workflow_id
                """  # nosec B608

            workflow_id = await self.postgres.fetchval(query, *values)

            # Invalidate cache
            self._invalidate_cache(str(execution_id))
            if workflow_id:
                self._invalidate_cache(str(workflow_id))

            logger.debug(f'Updated execution {execution_id} status to {status}')
            return True

        except Exception as e:
            logger.error(f'Failed to update execution status for {execution_id}: {e}')
            return False

    async def get_success_rate(
        self, workflow_id: UUID, days: int = 7, user_id: str | None = None
    ) -> float:
        """
        Calculate the success rate for a workflow over a time period.

        Args:
            workflow_id: UUID of the workflow
            days: Number of days to analyze (default: 7)

        Returns:
            float: Success rate as a percentage (0.0 to 1.0)
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_success_rate')
            since = datetime.now() - timedelta(days=days)

            if user_id is not None:
                query = """
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'completed') as successful
                    FROM workflow_executions
                    WHERE workflow_id = $1 AND started_at >= $2 AND user_id = $3
                """
                result = await self.postgres.fetchrow(
                    query, workflow_id, since, user_id
                )
            else:
                query = """
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'completed') as successful
                    FROM workflow_executions
                    WHERE workflow_id = $1 AND started_at >= $2
                """
                result = await self.postgres.fetchrow(query, workflow_id, since)

            if not result or result['total'] == 0:
                return 0.0

            success_rate = result['successful'] / result['total']
            return success_rate

        except Exception as e:
            logger.error(
                f'Failed to calculate success rate for workflow {workflow_id}: {e}'
            )
            return 0.0

    async def get_execution_statistics(
        self, workflow_id: UUID, days: int = 7, user_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get comprehensive execution statistics for a workflow.

        Args:
            workflow_id: UUID of the workflow
            days: Number of days to analyze (default: 7)

        Returns:
            dict[str, Any]: Dictionary containing execution statistics
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_execution_statistics')
            since = datetime.now() - timedelta(days=days)

            if user_id is not None:
                query = """
                    SELECT
                        COUNT(*) as total_executions,
                        COUNT(*) FILTER (WHERE status = 'completed') as successful,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        COUNT(*) FILTER (WHERE status = 'running') as running,
                        AVG(
                            EXTRACT(EPOCH FROM (completed_at - started_at))
                        ) FILTER (WHERE completed_at IS NOT NULL) as avg_duration_seconds,
                        MIN(started_at) as first_execution,
                        MAX(started_at) as last_execution
                    FROM workflow_executions
                    WHERE workflow_id = $1 AND started_at >= $2 AND user_id = $3
                """
                result = await self.postgres.fetchrow(
                    query, workflow_id, since, user_id
                )
            else:
                query = """
                    SELECT
                        COUNT(*) as total_executions,
                        COUNT(*) FILTER (WHERE status = 'completed') as successful,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        COUNT(*) FILTER (WHERE status = 'running') as running,
                        AVG(
                            EXTRACT(EPOCH FROM (completed_at - started_at))
                        ) FILTER (WHERE completed_at IS NOT NULL) as avg_duration_seconds,
                        MIN(started_at) as first_execution,
                        MAX(started_at) as last_execution
                    FROM workflow_executions
                    WHERE workflow_id = $1 AND started_at >= $2
                """
                result = await self.postgres.fetchrow(query, workflow_id, since)

            if not result:
                return {}

            stats = dict(result)

            # Calculate success rate
            if stats['total_executions'] > 0:
                stats['success_rate'] = stats['successful'] / stats['total_executions']
            else:
                stats['success_rate'] = 0.0

            return stats

        except Exception as e:
            logger.error(
                f'Failed to get execution statistics for workflow {workflow_id}: {e}'
            )
            return {}

    async def get_failed_executions(
        self, workflow_id: UUID, limit: int = 10, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get recent failed executions for debugging.

        Args:
            workflow_id: UUID of the workflow
            limit: Maximum number of failed executions to return

        Returns:
            list[dict[str, Any]]: List of failed execution records
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_failed_executions')
            if user_id is not None:
                query = """
                    SELECT * FROM workflow_executions
                    WHERE workflow_id = $1 AND status = 'failed' AND user_id = $3
                    ORDER BY started_at DESC
                    LIMIT $2
                """
                results = await self.postgres.fetch(query, workflow_id, limit, user_id)
            else:
                query = """
                    SELECT * FROM workflow_executions
                    WHERE workflow_id = $1 AND status = 'failed'
                    ORDER BY started_at DESC
                    LIMIT $2
                """
                results = await self.postgres.fetch(query, workflow_id, limit)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(
                f'Failed to get failed executions for workflow {workflow_id}: {e}'
            )
            return []

    async def get_running_executions(
        self,
        workflow_id: UUID | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all currently running executions.

        Args:
            workflow_id: Optional workflow UUID to filter by

        Returns:
            list[dict[str, Any]]: List of running execution records
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_running_executions')
            if workflow_id:
                if user_id is not None:
                    query = """
                        SELECT * FROM workflow_executions
                        WHERE workflow_id = $1 AND status = 'running' AND user_id = $2
                        ORDER BY started_at DESC
                    """
                    results = await self.postgres.fetch(query, workflow_id, user_id)
                else:
                    query = """
                        SELECT * FROM workflow_executions
                        WHERE workflow_id = $1 AND status = 'running'
                        ORDER BY started_at DESC
                    """
                    results = await self.postgres.fetch(query, workflow_id)
            else:
                if user_id is not None:
                    query = """
                        SELECT * FROM workflow_executions
                        WHERE status = 'running' AND user_id = $1
                        ORDER BY started_at DESC
                    """
                    results = await self.postgres.fetch(query, user_id)
                else:
                    query = """
                        SELECT * FROM workflow_executions
                        WHERE status = 'running'
                        ORDER BY started_at DESC
                    """
                    results = await self.postgres.fetch(query)

            return [dict(row) for row in results]

        except Exception as e:  # noqa: F841
            logger.error('Failed to get running executions: {e}')
            return []

    async def update_results(
        self, execution_id: UUID, results: dict[str, Any], user_id: str | None = None
    ) -> bool:
        """
        Update the results of a workflow execution.

        Args:
            execution_id: Execution UUID
            results: JSONB results data to store

        Returns:
            bool: True if successful, False otherwise
        """
        return await self.update(execution_id, {'results': results}, user_id=user_id)

    async def get_average_duration(
        self, workflow_id: UUID, days: int = 7, user_id: str | None = None
    ) -> float | None:
        """
        Get average execution duration in seconds.

        Args:
            workflow_id: UUID of the workflow
            days: Number of days to analyze (default: 7)

        Returns:
            Optional[float]: Average duration in seconds or None
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_average_duration')
            since = datetime.now() - timedelta(days=days)

            if user_id is not None:
                query = """
                    SELECT AVG(
                        EXTRACT(EPOCH FROM (completed_at - started_at))
                    ) as avg_duration
                    FROM workflow_executions
                    WHERE workflow_id = $1
                      AND started_at >= $2
                      AND completed_at IS NOT NULL
                      AND status = 'completed'
                      AND user_id = $3
                """
                result = await self.postgres.fetchval(
                    query, workflow_id, since, user_id
                )
            else:
                query = """
                    SELECT AVG(
                        EXTRACT(EPOCH FROM (completed_at - started_at))
                    ) as avg_duration
                    FROM workflow_executions
                    WHERE workflow_id = $1
                      AND started_at >= $2
                      AND completed_at IS NOT NULL
                      AND status = 'completed'
                """
                result = await self.postgres.fetchval(query, workflow_id, since)
            return result

        except Exception as e:
            logger.error(
                f'Failed to get average duration for workflow {workflow_id}: {e}'
            )
            return None
