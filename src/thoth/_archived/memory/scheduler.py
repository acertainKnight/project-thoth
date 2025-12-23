"""
Memory Scheduler

This module provides scheduling functionality for memory management tasks,
including episodic memory summarization and archival maintenance.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.memory.store import ThothMemoryStore
from thoth.memory.summarization import MemorySummarizationJob
from thoth.config import config


class MemorySchedulerError(Exception):
    """Exception raised for errors in the memory scheduler."""

    pass


class MemoryJobConfig:
    """Configuration for memory management jobs."""

    def __init__(
        self,
        enabled: bool = True,
        interval_hours: int = 24,
        time_of_day: str | None = None,
        days_of_week: list[int] | None = None,
        job_parameters: dict[str, Any] | None = None,
    ):
        """
        Initialize memory job configuration.

        Args:
            enabled: Whether the job is enabled
            interval_hours: Interval between job runs in hours
            time_of_day: Preferred time of day to run (HH:MM format)
            days_of_week: List of weekdays (0=Monday, 6=Sunday)
            job_parameters: Additional parameters for the job
        """
        self.enabled = enabled
        self.interval_hours = interval_hours
        self.time_of_day = time_of_day
        self.days_of_week = days_of_week or []
        self.job_parameters = job_parameters or {}


class MemoryScheduler:
    """
    Scheduler for memory management tasks.

    Manages the scheduling and execution of memory-related jobs
    such as episodic summarization and memory cleanup.
    """

    def __init__(
        self, memory_store: ThothMemoryStore, schedule_file: str | Path | None = None
    ):
        """
        Initialize the Memory Scheduler.

        Args:
            memory_store: ThothMemoryStore instance
            schedule_file: Path to file for storing schedule state
        """
        self.config = config
        self.memory_store = memory_store

        # Schedule state file
        self.schedule_file = Path(
            schedule_file or (self.config.agent_storage_dir / 'memory_schedule.json')
        )
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)

        # Scheduler state
        self.running = False
        self.scheduler_thread = None
        self.schedule_state = self._load_schedule_state()

        # Available jobs
        self.available_jobs = {
            'episodic_summarization': {
                'description': 'Summarize episodic memories and transfer to archival storage',
                'job_class': MemorySummarizationJob,
                'default_config': MemoryJobConfig(
                    enabled=True,
                    interval_hours=168,  # Weekly
                    time_of_day='02:00',  # 2 AM
                    job_parameters={
                        'analysis_window_hours': 168,  # 1 week
                        'min_memories_threshold': 10,
                        'cleanup_after_summary': False,
                    },
                ),
            }
        }

        # Job instances
        self.job_instances: dict[str, Any] = {}

        logger.info(
            f'Memory scheduler initialized with schedule file: {self.schedule_file}'
        )

    def start(self) -> None:
        """
        Start the memory scheduler.

        Raises:
            MemorySchedulerError: If scheduler is already running.
        """
        if self.running:
            raise MemorySchedulerError('Memory scheduler is already running')

        self.running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()

        logger.info('Memory scheduler started')

    def stop(self) -> None:
        """Stop the memory scheduler."""
        if not self.running:
            return

        self.running = False

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10.0)

        logger.info('Memory scheduler stopped')

    def add_job(self, job_name: str, config: MemoryJobConfig) -> None:
        """
        Add a memory job to the scheduler.

        Args:
            job_name: Name of the job to add
            config: MemoryJobConfig for the job

        Raises:
            MemorySchedulerError: If job name is not available
        """
        if job_name not in self.available_jobs:
            raise MemorySchedulerError(f'Unknown job: {job_name}')

        # Create job instance
        job_info = self.available_jobs[job_name]
        job_class = job_info['job_class']

        # Initialize job with parameters
        job_params = config.job_parameters.copy()
        if job_name == 'episodic_summarization':
            self.job_instances[job_name] = job_class(
                memory_store=self.memory_store,
                analysis_window_hours=job_params.get('analysis_window_hours', 168),
                min_memories_threshold=job_params.get('min_memories_threshold', 10),
                cleanup_after_summary=job_params.get('cleanup_after_summary', False),
            )

        # Add to schedule state
        self.schedule_state[job_name] = {
            'enabled': config.enabled,
            'interval_hours': config.interval_hours,
            'time_of_day': config.time_of_day,
            'days_of_week': config.days_of_week,
            'job_parameters': config.job_parameters,
            'last_run': None,
            'next_run': self._calculate_next_run(config) if config.enabled else None,
            'run_count': 0,
            'last_result': None,
        }

        self._save_schedule_state()
        logger.info(f'Added memory job: {job_name}')

    def remove_job(self, job_name: str) -> None:
        """
        Remove a job from the scheduler.

        Args:
            job_name: Name of the job to remove
        """
        if job_name in self.schedule_state:
            del self.schedule_state[job_name]
            self._save_schedule_state()

        if job_name in self.job_instances:
            del self.job_instances[job_name]

        logger.info(f'Removed memory job: {job_name}')

    def update_job_config(self, job_name: str, config: MemoryJobConfig) -> None:
        """
        Update the configuration for an existing job.

        Args:
            job_name: Name of the job to update
            config: New MemoryJobConfig for the job
        """
        if job_name not in self.schedule_state:
            logger.warning(f'Job {job_name} not found in schedule')
            return

        # Update schedule state
        self.schedule_state[job_name].update(
            {
                'enabled': config.enabled,
                'interval_hours': config.interval_hours,
                'time_of_day': config.time_of_day,
                'days_of_week': config.days_of_week,
                'job_parameters': config.job_parameters,
                'next_run': self._calculate_next_run(config)
                if config.enabled
                else None,
            }
        )

        # Recreate job instance if parameters changed
        if job_name in self.job_instances:
            job_info = self.available_jobs[job_name]
            job_class = job_info['job_class']
            job_params = config.job_parameters.copy()

            if job_name == 'episodic_summarization':
                self.job_instances[job_name] = job_class(
                    memory_store=self.memory_store,
                    analysis_window_hours=job_params.get('analysis_window_hours', 168),
                    min_memories_threshold=job_params.get('min_memories_threshold', 10),
                    cleanup_after_summary=job_params.get(
                        'cleanup_after_summary', False
                    ),
                )

        self._save_schedule_state()
        logger.info(f'Updated memory job config: {job_name}')

    def run_job_now(self, job_name: str, user_id: str | None = None) -> dict[str, Any]:
        """
        Run a specific job immediately, outside of its schedule.

        Args:
            job_name: Name of the job to run
            user_id: Optional user ID for user-specific jobs

        Returns:
            Dict with job results
        """
        try:
            if job_name not in self.job_instances:
                return {'error': f'Job {job_name} not configured'}

            logger.info(f'Running memory job {job_name} immediately')

            job_instance = self.job_instances[job_name]

            # Run the appropriate method based on job type
            if job_name == 'episodic_summarization':
                if user_id:
                    result = job_instance.run_summarization(user_id)
                else:
                    result = job_instance.run_for_all_users()

            # Update schedule state
            if job_name in self.schedule_state:
                self.schedule_state[job_name]['last_run'] = datetime.now().isoformat()
                self.schedule_state[job_name]['run_count'] += 1
                self.schedule_state[job_name]['last_result'] = {
                    'status': result.get('status'),
                    'summary': self._summarize_job_result(job_name, result),
                }
                self._save_schedule_state()

            logger.info(f'Memory job {job_name} completed: {result.get("status")}')
            return result

        except Exception as e:
            logger.error(f'Error running memory job {job_name}: {e}')
            return {'error': str(e)}

    def get_schedule_status(self) -> dict[str, Any]:
        """
        Get the current status of all scheduled memory jobs.

        Returns:
            Dict with schedule status information
        """
        jobs_status = []

        for job_name, schedule_info in self.schedule_state.items():
            job_description = self.available_jobs.get(job_name, {}).get(
                'description', 'Unknown job'
            )

            jobs_status.append(
                {
                    'name': job_name,
                    'description': job_description,
                    'enabled': schedule_info.get('enabled', False),
                    'interval_hours': schedule_info.get('interval_hours'),
                    'time_of_day': schedule_info.get('time_of_day'),
                    'days_of_week': schedule_info.get('days_of_week'),
                    'last_run': schedule_info.get('last_run'),
                    'next_run': schedule_info.get('next_run'),
                    'run_count': schedule_info.get('run_count', 0),
                    'last_result': schedule_info.get('last_result'),
                    'configured': job_name in self.job_instances,
                }
            )

        return {
            'running': self.running,
            'total_jobs': len(self.schedule_state),
            'enabled_jobs': sum(
                1 for j in self.schedule_state.values() if j.get('enabled', False)
            ),
            'jobs': jobs_status,
        }

    def get_available_jobs(self) -> dict[str, Any]:
        """
        Get information about available memory jobs.

        Returns:
            Dict with available job information
        """
        return {
            job_name: {
                'description': job_info['description'],
                'default_config': {
                    'enabled': job_info['default_config'].enabled,
                    'interval_hours': job_info['default_config'].interval_hours,
                    'time_of_day': job_info['default_config'].time_of_day,
                    'days_of_week': job_info['default_config'].days_of_week,
                    'job_parameters': job_info['default_config'].job_parameters,
                },
            }
            for job_name, job_info in self.available_jobs.items()
        }

    def _scheduler_loop(self) -> None:
        """Main scheduler loop that runs in a separate thread."""
        logger.info('Memory scheduler loop started')

        while self.running:
            try:
                self._check_and_run_scheduled_jobs()

                # Sleep for 1 hour before checking again
                # Memory jobs typically run less frequently than discovery jobs
                time.sleep(3600)

            except Exception as e:
                logger.error(f'Error in memory scheduler loop: {e}')
                time.sleep(3600)  # Continue after error

        logger.info('Memory scheduler loop stopped')

    def _check_and_run_scheduled_jobs(self) -> None:
        """Check for jobs that need to run and execute them."""
        current_time = datetime.now()

        for job_name, schedule_info in self.schedule_state.items():
            try:
                # Skip if not enabled or not configured
                if (
                    not schedule_info.get('enabled', False)
                    or job_name not in self.job_instances
                ):
                    continue

                # Check if it's time to run
                next_run_str = schedule_info.get('next_run')
                if not next_run_str:
                    continue

                next_run = datetime.fromisoformat(next_run_str)

                if current_time >= next_run:
                    logger.info(f'Running scheduled memory job: {job_name}')

                    # Run the job
                    result = self.run_job_now(job_name)

                    # Update schedule state
                    schedule_info['last_run'] = current_time.isoformat()
                    schedule_info['run_count'] = schedule_info.get('run_count', 0) + 1
                    schedule_info['last_result'] = {
                        'status': result.get('status'),
                        'summary': self._summarize_job_result(job_name, result),
                    }

                    # Calculate next run time
                    config = MemoryJobConfig(
                        enabled=schedule_info['enabled'],
                        interval_hours=schedule_info['interval_hours'],
                        time_of_day=schedule_info.get('time_of_day'),
                        days_of_week=schedule_info.get('days_of_week', []),
                        job_parameters=schedule_info.get('job_parameters', {}),
                    )
                    schedule_info['next_run'] = self._calculate_next_run(config)

                    logger.info(f'Scheduled memory job completed: {job_name}')

            except Exception as e:
                logger.error(f'Error running scheduled memory job {job_name}: {e}')

        # Save updated schedule state
        self._save_schedule_state()

    def _calculate_next_run(self, config: MemoryJobConfig) -> str:
        """
        Calculate the next run time for a job configuration.

        Args:
            config: MemoryJobConfig to calculate next run for

        Returns:
            ISO format timestamp of next run
        """
        if not config.enabled:
            return (datetime.now() + timedelta(days=365)).isoformat()  # Far future

        current_time = datetime.now()
        next_run = current_time + timedelta(hours=config.interval_hours)

        # Apply time of day preference
        if config.time_of_day:
            try:
                hour, minute = map(int, config.time_of_day.split(':'))
                next_run = next_run.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

                # If the time has already passed today, move to the next interval
                if next_run <= current_time:
                    next_run += timedelta(hours=config.interval_hours)

            except ValueError:
                logger.warning(f'Invalid time_of_day format: {config.time_of_day}')

        # Apply days of week preference
        if config.days_of_week:
            # Find the next valid day
            days_ahead = 0
            while next_run.weekday() not in config.days_of_week:
                next_run += timedelta(days=1)
                days_ahead += 1

                # Prevent infinite loop
                if days_ahead > 7:
                    break

        return next_run.isoformat()

    def _summarize_job_result(self, job_name: str, result: dict[str, Any]) -> str:
        """Create a summary of job execution results."""
        status = result.get('status', 'unknown')

        if job_name == 'episodic_summarization':
            if status == 'success':
                summaries = result.get('summaries_created', 0)
                memories = result.get('memories_analyzed', 0)
                return f'Created {summaries} summaries from {memories} memories'
            elif status == 'insufficient_memories':
                return f'Insufficient memories ({result.get("memory_count", 0)})'
            elif status == 'completed':
                total_summaries = result.get('total_summaries_created', 0)
                successful_users = result.get('successful_users', 0)
                return f'Processed {successful_users} users, created {total_summaries} summaries'

        return f'Status: {status}'

    def _load_schedule_state(self) -> dict[str, Any]:
        """Load schedule state from file."""
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f'Error loading memory schedule state: {e}')

        return {}

    def _save_schedule_state(self) -> None:
        """Save schedule state to file."""
        try:
            with open(self.schedule_file, 'w') as f:
                json.dump(self.schedule_state, f, indent=2)
        except Exception as e:
            logger.error(f'Error saving memory schedule state: {e}')

    def initialize_default_jobs(self) -> None:
        """Initialize default memory jobs with their default configurations."""
        for job_name, job_info in self.available_jobs.items():
            if job_name not in self.schedule_state:
                logger.info(f'Initializing default job: {job_name}')
                self.add_job(job_name, job_info['default_config'])

    def get_job_history(self, job_name: str, limit: int = 10) -> list[dict[str, Any]]:  # noqa: ARG002
        """
        Get execution history for a specific job.

        Note: This is a basic implementation. A production system would
        store detailed execution history in a separate log or database.

        Args:
            job_name: Name of the job
            limit: Maximum number of history entries to return

        Returns:
            List of job execution history entries
        """
        if job_name not in self.schedule_state:
            return []

        schedule_info = self.schedule_state[job_name]
        last_result = schedule_info.get('last_result')

        if last_result:
            return [
                {
                    'job_name': job_name,
                    'execution_time': schedule_info.get('last_run'),
                    'status': last_result.get('status'),
                    'summary': last_result.get('summary'),
                    'run_number': schedule_info.get('run_count', 0),
                }
            ]

        return []
