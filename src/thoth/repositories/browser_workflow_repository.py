"""
Browser workflow repository for managing browser_workflows table.

This module provides methods for managing browser-based discovery workflows,
including CRUD operations, execution statistics, and health monitoring.
"""

from typing import Any, Optional  # noqa: I001
from uuid import UUID
from datetime import datetime
from loguru import logger

from thoth.repositories.base import BaseRepository


class BrowserWorkflowRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing browser workflow records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize browser workflow repository."""
        super().__init__(postgres_service, table_name='browser_workflows', **kwargs)

    async def create(self, workflow_data: dict[str, Any]) -> Optional[UUID]:  # noqa: UP007
        """
        Create a new browser workflow.

        Args:
            workflow_data: Dictionary containing workflow configuration

        Returns:
            Optional[UUID]: ID of created workflow or None
        """
        try:
            # Validate required fields
            required_fields = [
                'name',
                'website_domain',
                'start_url',
                'extraction_rules',
            ]
            for field in required_fields:
                if field not in workflow_data:
                    logger.error(f'Missing required field: {field}')
                    return None

            # Build column and value lists
            columns = list(workflow_data.keys())
            placeholders = [f'${i + 1}' for i in range(len(columns))]
            values = [workflow_data[col] for col in columns]

            query = f"""
                INSERT INTO browser_workflows ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """

            result = await self.postgres.fetchval(query, *values)

            # Invalidate cache
            self._invalidate_cache()

            logger.debug(f'Created browser workflow: {result}')
            return result

        except Exception as e:
            logger.error(f'Failed to create browser workflow: {e}')
            return None

    async def get_by_id(self, workflow_id: UUID) -> Optional[dict[str, Any]]:  # noqa: UP007
        """
        Get a workflow by ID.

        Args:
            workflow_id: Workflow UUID

        Returns:
            Optional[dict[str, Any]]: Workflow data or None
        """
        cache_key = self._cache_key('id', str(workflow_id))
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM browser_workflows WHERE id = $1'
            result = await self.postgres.fetchrow(query, workflow_id)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get workflow by ID {workflow_id}: {e}')
            return None

    async def get_by_name(self, name: str) -> Optional[dict[str, Any]]:  # noqa: UP007
        """
        Get a workflow by name.

        Args:
            name: Workflow name

        Returns:
            Optional[dict[str, Any]]: Workflow data or None
        """
        cache_key = self._cache_key('name', name)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM browser_workflows WHERE name = $1'
            result = await self.postgres.fetchrow(query, name)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get workflow by name {name}: {e}')
            return None

    async def get_active_workflows(self) -> list[dict[str, Any]]:
        """
        Get all active workflows.

        Returns:
            list[dict[str, Any]]: List of active workflows
        """
        cache_key = self._cache_key('active')
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM browser_workflows
                WHERE is_active = true
                ORDER BY name ASC
            """

            results = await self.postgres.fetch(query)
            data = [dict(row) for row in results]

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get active workflows: {e}')
            return []

    async def update(self, workflow_id: UUID, updates: dict[str, Any]) -> bool:
        """
        Update a workflow.

        Args:
            workflow_id: Workflow UUID
            updates: Dictionary of fields to update

        Returns:
            bool: True if successful
        """
        try:
            if not updates:
                return True

            # Build SET clause
            set_clauses = [f'{col} = ${i + 2}' for i, col in enumerate(updates.keys())]
            values = [workflow_id] + list(updates.values())  # noqa: RUF005

            # Always update updated_at timestamp
            set_clauses.append(f'updated_at = ${len(values) + 1}')
            values.append(datetime.now())

            query = f"""
                UPDATE browser_workflows
                SET {', '.join(set_clauses)}
                WHERE id = $1
            """

            await self.postgres.execute(query, *values)

            # Invalidate cache
            self._invalidate_cache(str(workflow_id))

            logger.debug(f'Updated workflow {workflow_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to update workflow {workflow_id}: {e}')
            return False

    async def delete(self, workflow_id: UUID) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            bool: True if successful
        """
        try:
            query = 'DELETE FROM browser_workflows WHERE id = $1'
            await self.postgres.execute(query, workflow_id)

            # Invalidate cache
            self._invalidate_cache(str(workflow_id))

            logger.info(f'Deleted workflow: {workflow_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to delete workflow {workflow_id}: {e}')
            return False

    async def update_statistics(
        self,
        workflow_id: UUID,
        success: bool,
        articles_found: int,
        duration_ms: int,
    ) -> bool:
        """
        Update execution statistics for a workflow.

        Args:
            workflow_id: Workflow UUID
            success: Whether execution was successful
            articles_found: Number of articles extracted
            duration_ms: Execution duration in milliseconds

        Returns:
            bool: True if successful
        """
        try:
            now = datetime.now()

            if success:
                query = """
                    UPDATE browser_workflows
                    SET total_executions = total_executions + 1,
                        successful_executions = successful_executions + 1,
                        total_articles_extracted = total_articles_extracted + $1,
                        average_execution_time_ms = CASE
                            WHEN average_execution_time_ms IS NULL THEN $2
                            ELSE (average_execution_time_ms * total_executions + $2) /
                                 (total_executions + 1)
                        END,
                        last_executed_at = $3,
                        last_success_at = $3,
                        updated_at = $3
                    WHERE id = $4
                """
                await self.postgres.execute(
                    query, articles_found, duration_ms, now, workflow_id
                )
            else:
                query = """
                    UPDATE browser_workflows
                    SET total_executions = total_executions + 1,
                        failed_executions = failed_executions + 1,
                        last_executed_at = $1,
                        last_failure_at = $1,
                        updated_at = $1
                    WHERE id = $2
                """
                await self.postgres.execute(query, now, workflow_id)

            # Invalidate cache
            self._invalidate_cache(str(workflow_id))

            logger.debug(
                f'Updated statistics for workflow {workflow_id}: '
                f'success={success}, articles={articles_found}'
            )
            return True

        except Exception as e:
            logger.error(f'Failed to update statistics for workflow {workflow_id}: {e}')
            return False

    async def update_health_status(self, workflow_id: UUID, status: str) -> bool:
        """
        Update health status for a workflow.

        Args:
            workflow_id: Workflow UUID
            status: Health status ('active', 'degraded', 'down', 'unknown')

        Returns:
            bool: True if successful
        """
        try:
            valid_statuses = ['active', 'degraded', 'down', 'unknown']
            if status not in valid_statuses:
                logger.warning(
                    f'Invalid health status: {status}. Must be one of {valid_statuses}'
                )
                return False

            query = """
                UPDATE browser_workflows
                SET health_status = $1,
                    updated_at = $2
                WHERE id = $3
            """

            await self.postgres.execute(query, status, datetime.now(), workflow_id)

            # Invalidate cache
            self._invalidate_cache(str(workflow_id))

            logger.debug(f'Updated health status for workflow {workflow_id}: {status}')
            return True

        except Exception as e:
            logger.error(
                f'Failed to update health status for workflow {workflow_id}: {e}'
            )
            return False

    async def get_by_domain(self, domain: str) -> list[dict[str, Any]]:
        """
        Get workflows by domain.

        Args:
            domain: Website domain

        Returns:
            list[dict[str, Any]]: List of workflows for the domain
        """
        cache_key = self._cache_key('domain', domain)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM browser_workflows
                WHERE website_domain = $1
                ORDER BY name ASC
            """

            results = await self.postgres.fetch(query, domain)
            data = [dict(row) for row in results]

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get workflows by domain {domain}: {e}')
            return []

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get overall workflow statistics.

        Returns:
            dict[str, Any]: Aggregated statistics across all workflows
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_workflows,
                    COUNT(*) FILTER (WHERE is_active = true) as active_workflows,
                    COUNT(*) FILTER (WHERE health_status = 'active') as healthy_workflows,
                    COUNT(*) FILTER (WHERE health_status = 'degraded') as degraded_workflows,
                    COUNT(*) FILTER (WHERE health_status = 'down') as down_workflows,
                    SUM(total_executions) as total_executions,
                    SUM(successful_executions) as successful_executions,
                    SUM(failed_executions) as failed_executions,
                    SUM(total_articles_extracted) as total_articles_extracted,
                    AVG(average_execution_time_ms) as avg_execution_time_ms
                FROM browser_workflows
            """

            result = await self.postgres.fetchrow(query)
            return dict(result) if result else {}

        except Exception as e:
            logger.error(f'Failed to get workflow statistics: {e}')
            return {}

    async def deactivate(self, workflow_id: UUID) -> bool:
        """
        Deactivate a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            bool: True if successful
        """
        return await self.update(workflow_id, {'is_active': False})

    async def activate(self, workflow_id: UUID) -> bool:
        """
        Activate a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            bool: True if successful
        """
        return await self.update(workflow_id, {'is_active': True})

    async def get_workflows_due_for_run(
        self, hours_since_last_run: int = 24
    ) -> list[dict[str, Any]]:
        """
        Get workflows that are due for execution based on time since last run.

        Returns active workflows where last_executed_at is older than the specified
        hours, or workflows that have never been executed.

        Args:
            hours_since_last_run: Number of hours since last execution to consider
                                 a workflow due for run (default: 24 hours for daily schedule)

        Returns:
            list[dict[str, Any]]: List of workflows due for execution
        """  # noqa: W505
        cache_key = self._cache_key('due_for_run', str(hours_since_last_run))
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM browser_workflows
                WHERE is_active = true
                  AND (
                    last_executed_at IS NULL
                    OR last_executed_at < NOW() - ($1 || ' hours')::INTERVAL
                  )
                ORDER BY
                    last_executed_at ASC NULLS FIRST,
                    name ASC
            """

            results = await self.postgres.fetch(query, hours_since_last_run)
            data = [dict(row) for row in results]

            # Cache for shorter time since this is time-sensitive
            self._set_in_cache(cache_key, data, ttl=300)  # 5 minutes

            logger.debug(
                f'Found {len(data)} workflows due for run '
                f'(>{hours_since_last_run}h since last execution)'
            )
            return data

        except Exception as e:
            logger.error(f'Failed to get workflows due for run: {e}')
            return []
