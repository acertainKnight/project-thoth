"""
Background task management for long-running operations.

This module provides infrastructure for running tasks asynchronously
without blocking HTTP connections or agent interactions.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from dataclasses import dataclass, field

from thoth.services.base import BaseService


class TaskStatus(str, Enum):
    """Status of a background task."""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class BackgroundTask:
    """Represents a background task."""

    task_id: str
    name: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)


class BackgroundTaskManager(BaseService):
    """
    Manages background tasks for long-running operations.

    This service allows operations to be triggered asynchronously and
    provides status tracking for in-progress and completed tasks.
    """

    def __init__(self):
        """Initialize the background task manager."""
        super().__init__()
        self.tasks: dict[str, BackgroundTask] = {}
        self._task_futures: dict[str, asyncio.Task] = {}

    def create_task(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> str:
        """
        Create and start a background task.

        Args:
            name: Human-readable task name
            func: Function to execute (can be sync or async)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            str: Task ID for tracking
        """
        task_id = str(uuid.uuid4())

        # Create task record
        task = BackgroundTask(
            task_id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self.tasks[task_id] = task

        # Start the task
        asyncio_task = asyncio.create_task(
            self._run_task(task_id, func, *args, **kwargs)
        )
        self._task_futures[task_id] = asyncio_task

        self.logger.info(f'Created background task {task_id}: {name}')
        return task_id

    async def _run_task(
        self,
        task_id: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> None:
        """
        Execute a background task and update its status.

        Args:
            task_id: Task identifier
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        task = self.tasks[task_id]

        try:
            # Update status to running
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc)
            self.logger.info(f'Starting task {task_id}: {task.name}')

            # Execute the function (handle both sync and async)
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                # Run sync function in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, func, *args, **kwargs)

            # Update with success
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = result
            self.logger.info(
                f'Task {task_id} completed successfully in '
                f'{(task.completed_at - task.started_at).total_seconds():.2f}s'
            )

        except Exception as e:
            # Update with failure
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.error = str(e)
            self.logger.error(
                f'Task {task_id} failed: {e}', exc_info=True
            )

        finally:
            # Clean up the future
            if task_id in self._task_futures:
                del self._task_futures[task_id]

    def get_task_status(self, task_id: str) -> BackgroundTask | None:
        """
        Get the status of a background task.

        Args:
            task_id: Task identifier

        Returns:
            BackgroundTask | None: Task status or None if not found
        """
        return self.tasks.get(task_id)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        limit: int = 50,
    ) -> list[BackgroundTask]:
        """
        List background tasks.

        Args:
            status: Optional status filter
            limit: Maximum number of tasks to return

        Returns:
            list[BackgroundTask]: List of tasks
        """
        tasks = list(self.tasks.values())

        # Filter by status if specified
        if status:
            tasks = [t for t in tasks if t.status == status]

        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks[:limit]

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """
        Remove completed tasks older than specified age.

        Args:
            max_age_hours: Maximum age in hours for completed tasks

        Returns:
            int: Number of tasks removed
        """
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (max_age_hours * 3600)

        tasks_to_remove = [
            task_id
            for task_id, task in self.tasks.items()
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            and task.completed_at
            and task.completed_at.timestamp() < cutoff
        ]

        for task_id in tasks_to_remove:
            del self.tasks[task_id]

        if tasks_to_remove:
            self.logger.info(
                f'Cleaned up {len(tasks_to_remove)} old background tasks'
            )

        return len(tasks_to_remove)
