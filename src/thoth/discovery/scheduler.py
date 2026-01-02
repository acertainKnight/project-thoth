"""
Discovery scheduler for managing automated article discovery.

This module provides scheduling functionality for running discovery
sources on configurable cadences and managing the discovery workflow.
"""

import asyncio  # noqa: I001
import json  # noqa: F401
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.config import config
from thoth.utilities.schemas import DiscoverySource, ScheduleConfig


class DiscoverySchedulerError(Exception):
    """Exception raised for errors in the discovery scheduler."""

    pass


class DiscoveryScheduler:
    """
    Scheduler for automated article discovery.

    This class manages the scheduling and execution of discovery sources
    based on their configured cadences and time preferences.
    """

    def __init__(
        self,
        discovery_manager: DiscoveryManager | None = None,
        schedule_file: str | Path | None = None,
        research_question_service=None,
        discovery_orchestrator=None,
        event_loop=None,
    ):
        """
        Initialize the Discovery Scheduler.

        Args:
            discovery_manager: DiscoveryManager instance for running discovery.
            schedule_file: Path to file for storing schedule state.
            research_question_service: ResearchQuestionService for question scheduling.
            discovery_orchestrator: DiscoveryOrchestrator for running question-based discovery.
            event_loop: Event loop to use for async operations from sync thread.
                       If None, will use asyncio.run() (creates new loop per call).
        """  # noqa: W505
        self.config = config
        self.discovery_manager = discovery_manager or DiscoveryManager()
        self.research_question_service = research_question_service
        self.discovery_orchestrator = discovery_orchestrator
        self.event_loop = event_loop

        # Schedule state file
        self.schedule_file = Path(
            schedule_file or (self.config.agent_storage_dir / 'discovery_schedule.json')
        )
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)

        # Scheduler state
        self.running = False
        self.scheduler_thread = None
        self.schedule_state = self._load_schedule_state()

        logger.info(
            f'Discovery scheduler initialized with schedule file: {self.schedule_file}'
        )
        if self.event_loop:
            logger.info(
                'Scheduler configured to use provided event loop for async operations'
            )

    def start(self) -> None:
        """
        Start the discovery scheduler.

        Raises:
            DiscoverySchedulerError: If scheduler is already running.

        Example:
            >>> scheduler = DiscoveryScheduler()
            >>> scheduler.start()
            >>> # Scheduler runs in background
        """
        if self.running:
            raise DiscoverySchedulerError('Scheduler is already running')

        self.running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()

        logger.info('Discovery scheduler started')

    def stop(self) -> None:
        """
        Stop the discovery scheduler.

        Example:
            >>> scheduler.stop()
        """
        if not self.running:
            return

        self.running = False

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5.0)

        logger.info('Discovery scheduler stopped')

    def add_scheduled_source(
        self, source: DiscoverySource, schedule: ScheduleConfig
    ) -> None:
        """
        Add a source to the scheduler.

        Args:
            source: DiscoverySource to schedule.
            schedule: ScheduleConfig for the source.

        Example:
            >>> scheduler = DiscoveryScheduler()
            >>> source = DiscoverySource(name='arxiv_ml', ...)
            >>> schedule = ScheduleConfig(interval_minutes=60, enabled=True)
            >>> scheduler.add_scheduled_source(source, schedule)
        """
        # Update source with schedule config
        source.schedule_config = schedule

        # Create or update source in discovery manager
        try:
            existing_source = self.discovery_manager.get_source(source.name)
            if existing_source:
                self.discovery_manager.update_source(source)
            else:
                self.discovery_manager.create_source(source)
        except Exception as e:
            logger.error(f'Error adding source {source.name}: {e}')
            return

        # Add to schedule state
        self.schedule_state[source.name] = {
            'last_run': source.last_run,
            'next_run': self._calculate_next_run(source.schedule_config),
            'enabled': schedule.enabled,
            'interval_minutes': schedule.interval_minutes,
            'max_articles_per_run': schedule.max_articles_per_run,
            'time_of_day': schedule.time_of_day,
            'days_of_week': schedule.days_of_week,
        }

        self._save_schedule_state()
        logger.info(f'Added scheduled source: {source.name}')

    def remove_scheduled_source(self, source_name: str) -> None:
        """
        Remove a source from the scheduler.

        Args:
            source_name: Name of the source to remove.

        Example:
            >>> scheduler.remove_scheduled_source('arxiv_ml')
        """
        if source_name in self.schedule_state:
            del self.schedule_state[source_name]
            self._save_schedule_state()
            logger.info(f'Removed scheduled source: {source_name}')

    def update_source_schedule(
        self, source_name: str, schedule: ScheduleConfig
    ) -> None:
        """
        Update the schedule for an existing source.

        Args:
            source_name: Name of the source to update.
            schedule: New ScheduleConfig for the source.

        Example:
            >>> new_schedule = ScheduleConfig(interval_minutes=120, enabled=True)
            >>> scheduler.update_source_schedule('arxiv_ml', new_schedule)
        """
        if source_name not in self.schedule_state:
            logger.warning(f'Source {source_name} not found in schedule')
            return

        # Update source in discovery manager
        source = self.discovery_manager.get_source(source_name)
        if source:
            source.schedule_config = schedule
            self.discovery_manager.update_source(source)

        # Update schedule state
        self.schedule_state[source_name].update(
            {
                'next_run': self._calculate_next_run(schedule),
                'enabled': schedule.enabled,
                'interval_minutes': schedule.interval_minutes,
                'max_articles_per_run': schedule.max_articles_per_run,
                'time_of_day': schedule.time_of_day,
                'days_of_week': schedule.days_of_week,
            }
        )

        self._save_schedule_state()
        logger.info(f'Updated schedule for source: {source_name}')

    def get_schedule_status(self) -> dict[str, Any]:
        """
        Get the current status of all scheduled sources.

        Returns:
            dict[str, Any]: Schedule status information.

        Example:
            >>> status = scheduler.get_schedule_status()
            >>> print(f'Scheduler running: {status["running"]}')
            >>> for source in status['sources']:
            ...     print(f'{source["name"]}: next run at {source["next_run"]}')
        """
        sources_status = []

        for source_name, schedule_info in self.schedule_state.items():
            source = self.discovery_manager.get_source(source_name)

            sources_status.append(
                {
                    'name': source_name,
                    'enabled': schedule_info.get('enabled', False),
                    'last_run': schedule_info.get('last_run'),
                    'next_run': schedule_info.get('next_run'),
                    'interval_minutes': schedule_info.get('interval_minutes'),
                    'max_articles_per_run': schedule_info.get('max_articles_per_run'),
                    'source_active': source.is_active if source else False,
                    'source_type': source.source_type if source else None,
                }
            )

        return {
            'running': self.running,
            'total_sources': len(self.schedule_state),
            'enabled_sources': sum(
                1 for s in self.schedule_state.values() if s.get('enabled', False)
            ),
            'sources': sources_status,
        }

    def run_source_now(self, source_name: str) -> dict[str, Any]:
        """
        Run a specific source immediately, outside of its schedule.

        Args:
            source_name: Name of the source to run.

        Returns:
            dict[str, Any]: Results of the discovery run.

        Example:
            >>> result = scheduler.run_source_now('arxiv_ml')
            >>> print(f'Found {result["articles_found"]} articles')
        """
        try:
            logger.info(f'Running source {source_name} immediately')

            # Get max articles from schedule
            max_articles = None
            if source_name in self.schedule_state:
                max_articles = self.schedule_state[source_name].get(
                    'max_articles_per_run'
                )

            # Run discovery
            result = self.discovery_manager.run_discovery(
                source_name=source_name, max_articles=max_articles
            )

            # Update schedule state
            if source_name in self.schedule_state:
                self.schedule_state[source_name]['last_run'] = (
                    datetime.now().isoformat()
                )
                self._save_schedule_state()

            result_dict = result.model_dump()
            result_dict['success'] = len(result.errors) == 0
            return result_dict

        except Exception as e:
            logger.error(f'Error running source {source_name}: {e}')
            return {'success': False, 'error': str(e)}

    def _scheduler_loop(self) -> None:
        """
        Main scheduler loop that runs in a separate thread.
        """
        logger.info('Scheduler loop started')

        while self.running:
            try:
                # Check and run scheduled sources (existing functionality)
                self._check_and_run_scheduled_sources()

                # Check and run scheduled research questions (new functionality)
                self._check_and_run_scheduled_questions()

                # Sleep for 1 minute before checking again
                time.sleep(60)

            except Exception as e:
                logger.error(f'Error in scheduler loop: {e}')
                time.sleep(60)  # Continue after error

        logger.info('Scheduler loop stopped')

    def _check_and_run_scheduled_sources(self) -> None:
        """
        Check for sources that need to run and execute them.
        """
        current_time = datetime.now()

        for source_name, schedule_info in self.schedule_state.items():
            try:
                # Skip if not enabled
                if not schedule_info.get('enabled', False):
                    continue

                # Check if it's time to run
                next_run_str = schedule_info.get('next_run')
                if not next_run_str:
                    continue

                next_run = datetime.fromisoformat(next_run_str)

                if current_time >= next_run:
                    logger.info(
                        f'Running scheduled discovery for source: {source_name}'
                    )

                    # Run the source
                    max_articles = schedule_info.get('max_articles_per_run')
                    result = self.discovery_manager.run_discovery(
                        source_name=source_name, max_articles=max_articles
                    )

                    # Update schedule state
                    schedule_info['last_run'] = current_time.isoformat()

                    # Calculate next run time
                    source = self.discovery_manager.get_source(source_name)
                    if source and source.schedule_config:
                        schedule_info['next_run'] = self._calculate_next_run(
                            source.schedule_config
                        )

                    logger.info(
                        f'Scheduled discovery completed for {source_name}: '
                        f'{result.articles_found} found, {result.articles_downloaded} downloaded'
                    )

            except Exception as e:
                logger.error(f'Error running scheduled source {source_name}: {e}')

        # Save updated schedule state
        self._save_schedule_state()

    def _calculate_next_run(self, schedule: ScheduleConfig) -> str:
        """
        Calculate the next run time for a schedule configuration.

        Args:
            schedule: ScheduleConfig to calculate next run for.

        Returns:
            str: ISO format timestamp of next run.
        """
        if not schedule.enabled:
            return (datetime.now() + timedelta(days=365)).isoformat()  # Far future

        current_time = datetime.now()
        next_run = current_time + timedelta(minutes=schedule.interval_minutes)

        # Apply time of day preference
        if schedule.time_of_day:
            try:
                hour, minute = map(int, schedule.time_of_day.split(':'))
                next_run = next_run.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

                # If the time has already passed today, move to tomorrow
                if next_run <= current_time:
                    next_run += timedelta(days=1)

            except ValueError:
                logger.warning(f'Invalid time_of_day format: {schedule.time_of_day}')

        # Apply days of week preference
        if schedule.days_of_week:
            # Find the next valid day
            days_ahead = 0
            while next_run.weekday() not in schedule.days_of_week:
                next_run += timedelta(days=1)
                days_ahead += 1

                # Prevent infinite loop
                if days_ahead > 7:
                    break

        return next_run.isoformat()

    def _load_schedule_state(self) -> dict[str, Any]:
        """
        Load schedule state from PostgreSQL.

        Returns:
            dict[str, Any]: Schedule state dictionary.
        """
        try:
            return self._load_from_postgres()
        except Exception as e:
            logger.error(f'Error loading schedule state from PostgreSQL: {e}')
            return {}

    def _load_from_postgres(self) -> dict[str, Any]:
        """Load discovery schedule from PostgreSQL."""
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def load():
            conn = await asyncpg.connect(db_url)
            try:
                rows = await conn.fetch('SELECT * FROM discovery_schedule')
                schedule_state = {}
                for row in rows:
                    schedule_state[row['source_name']] = {
                        'last_run': row['last_run'],
                        'next_run': row['next_run'],
                        'enabled': row['enabled'],
                        'interval_minutes': row['interval_minutes'],
                        'max_articles_per_run': row['max_articles_per_run'],
                        'time_of_day': row['time_of_day'],
                        'days_of_week': row['days_of_week'],
                    }
                logger.info(
                    f'Loaded discovery schedule for {len(rows)} sources from PostgreSQL'
                )
                return schedule_state
            finally:
                await conn.close()

        # Use asyncio.run() to create a new event loop - safe from any thread
        try:
            return asyncio.run(load())
        except RuntimeError:
            # If there's already an event loop running, create a new one in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(load()))
                return future.result()

    def _save_schedule_state(self) -> None:
        """
        Save schedule state to PostgreSQL.
        """
        try:
            self._save_to_postgres()
        except Exception as e:
            logger.error(f'Error saving schedule state: {e}')

    def _save_to_postgres(self) -> None:
        """Save discovery schedule to PostgreSQL."""
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                for source_name, schedule_info in self.schedule_state.items():
                    await conn.execute(
                        """
                        INSERT INTO discovery_schedule (
                            source_name, last_run, next_run, enabled,
                            interval_minutes, max_articles_per_run, time_of_day, days_of_week
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (source_name) DO UPDATE SET
                            last_run = EXCLUDED.last_run,
                            next_run = EXCLUDED.next_run,
                            enabled = EXCLUDED.enabled,
                            interval_minutes = EXCLUDED.interval_minutes,
                            max_articles_per_run = EXCLUDED.max_articles_per_run,
                            time_of_day = EXCLUDED.time_of_day,
                            days_of_week = EXCLUDED.days_of_week
                    """,
                        source_name,
                        schedule_info.get('last_run'),
                        schedule_info.get('next_run'),
                        schedule_info.get('enabled'),
                        schedule_info.get('interval_minutes'),
                        schedule_info.get('max_articles_per_run'),
                        schedule_info.get('time_of_day'),
                        schedule_info.get('days_of_week'),
                    )
                logger.debug(
                    f'Saved discovery schedule for {len(self.schedule_state)} sources to PostgreSQL'
                )
            finally:
                await conn.close()

        # Use asyncio.run() to create a new event loop - safe from any thread
        try:
            asyncio.run(save())
        except RuntimeError:
            # If there's already an event loop running, create a new one in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(save()))
                future.result()

    def sync_with_discovery_manager(self) -> None:
        """
        Synchronize scheduler state with discovery manager sources.

        This method ensures that the scheduler is aware of all sources
        in the discovery manager and removes orphaned schedule entries.
        """
        try:
            # Get all sources from discovery manager
            all_sources = self.discovery_manager.list_sources()
            source_names = {source.name for source in all_sources}

            # Remove orphaned schedule entries
            orphaned = set(self.schedule_state.keys()) - source_names
            for orphaned_name in orphaned:
                logger.info(f'Removing orphaned schedule entry: {orphaned_name}')
                del self.schedule_state[orphaned_name]

            # Add missing schedule entries for sources with schedule configs
            for source in all_sources:
                if source.name not in self.schedule_state and source.schedule_config:
                    self.schedule_state[source.name] = {
                        'last_run': source.last_run,
                        'next_run': self._calculate_next_run(source.schedule_config),
                        'enabled': source.schedule_config.enabled,
                        'interval_minutes': source.schedule_config.interval_minutes,
                        'max_articles_per_run': source.schedule_config.max_articles_per_run,
                        'time_of_day': source.schedule_config.time_of_day,
                        'days_of_week': source.schedule_config.days_of_week,
                    }
                    logger.info(f'Added schedule entry for source: {source.name}')

            self._save_schedule_state()
            logger.info('Scheduler synchronized with discovery manager')

        except Exception as e:
            logger.error(f'Error synchronizing scheduler: {e}')

    def get_next_scheduled_runs(self, hours: int = 24) -> list[dict[str, Any]]:
        """
        Get upcoming scheduled runs within the specified time window.

        Args:
            hours: Number of hours to look ahead.

        Returns:
            list[dict[str, Any]]: List of upcoming runs with source info and times.

        Example:
            >>> upcoming = scheduler.get_next_scheduled_runs(12)
            >>> for run in upcoming:
            ...     print(f'{run["source_name"]} at {run["scheduled_time"]}')
        """
        current_time = datetime.now()
        cutoff_time = current_time + timedelta(hours=hours)

        upcoming_runs = []

        for source_name, schedule_info in self.schedule_state.items():
            if not schedule_info.get('enabled', False):
                continue

            next_run_str = schedule_info.get('next_run')
            if not next_run_str:
                continue

            try:
                next_run = datetime.fromisoformat(next_run_str)

                if current_time <= next_run <= cutoff_time:
                    upcoming_runs.append(
                        {
                            'source_name': source_name,
                            'scheduled_time': next_run_str,
                            'time_until_run': str(next_run - current_time),
                            'max_articles': schedule_info.get('max_articles_per_run'),
                            'interval_minutes': schedule_info.get('interval_minutes'),
                        }
                    )

            except ValueError:
                logger.warning(
                    f'Invalid next_run time for {source_name}: {next_run_str}'
                )

        # Sort by scheduled time
        upcoming_runs.sort(key=lambda x: x['scheduled_time'])

        return upcoming_runs

    def _check_and_run_scheduled_questions(self) -> None:
        """
        Check for research questions that need to run and execute them.

        This method bridges sync thread → async methods using asyncio.run_coroutine_threadsafe.
        """  # noqa: W505
        # Skip if research question service not configured
        if not self.research_question_service or not self.discovery_orchestrator:
            logger.debug(
                'Research question scheduling disabled (services not configured)'
            )
            return

        try:
            # Get questions due for discovery (async call from sync thread)
            if self.event_loop:
                # Use run_coroutine_threadsafe with provided event loop
                future = asyncio.run_coroutine_threadsafe(
                    self.research_question_service.get_questions_due_for_discovery(),
                    self.event_loop,
                )
                try:
                    questions_due = future.result(timeout=30)  # 30 second timeout
                except TimeoutError:
                    logger.error('Timeout getting questions due for discovery (30s)')
                    return
                except Exception as e:
                    logger.error(f'Error getting questions due: {e}', exc_info=True)
                    return
            else:
                # Fallback: Create new event loop (works but less efficient)
                questions_due = asyncio.run(
                    self.research_question_service.get_questions_due_for_discovery()
                )

            if not questions_due:
                logger.debug('No research questions due for discovery')
                return

            logger.info(
                f'Found {len(questions_due)} research questions due for discovery'
            )

            # Run discovery for each question
            for question in questions_due:
                try:
                    question_id = question['id']
                    question_name = question.get('name', 'Unknown')

                    logger.info(
                        f'Running scheduled discovery for research question: '
                        f'{question_name} ({question_id})'
                    )

                    # Run discovery (async call from sync thread)
                    if self.event_loop:
                        # Use run_coroutine_threadsafe with provided event loop
                        future = asyncio.run_coroutine_threadsafe(
                            self._run_question_discovery_async(question_id, question),
                            self.event_loop,
                        )
                        try:
                            result = future.result(
                                timeout=600
                            )  # 10 minute timeout for discovery
                        except TimeoutError:
                            logger.error(
                                f'Timeout running discovery for question {question_name} (10 min)'
                            )
                            result = {
                                'success': False,
                                'error': 'Discovery execution timeout (10 minutes)',
                            }
                        except Exception as e:
                            logger.error(f'Error running discovery: {e}', exc_info=True)
                            result = {'success': False, 'error': str(e)}
                    else:
                        # Fallback: Create new event loop
                        result = asyncio.run(
                            self._run_question_discovery_async(question_id, question)
                        )

                    if result.get('success'):
                        logger.info(
                            f'Scheduled discovery completed for question {question_name}: '
                            f'{result.get("articles_found", 0)} found, '
                            f'{result.get("articles_matched", 0)} matched'
                        )
                    else:
                        logger.error(
                            f'Scheduled discovery failed for question {question_name}: '
                            f'{result.get("error", "Unknown error")}'
                        )

                except Exception as e:
                    logger.error(
                        f'Error running scheduled question {question.get("name", question.get("id"))}: {e}',
                        exc_info=True,
                    )
                    # Continue with next question

        except Exception as e:
            logger.error(
                f'Error in _check_and_run_scheduled_questions: {e}', exc_info=True
            )

    async def _run_question_discovery_async(
        self, question_id: str, question: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Async helper method to run discovery and update statistics.

        This method:
        1. Runs discovery via orchestrator
        2. Updates last_run_at and next_run_at in database
        3. Logs execution to discovery_execution_log

        Args:
            question_id: Research question UUID
            question: Question record with schedule info

        Returns:
            Discovery result dictionary
        """
        start_time = time.time()

        try:
            # Run discovery
            result = await self.discovery_orchestrator.run_discovery_for_question(
                question_id=question_id
            )

            execution_time = time.time() - start_time

            # Update question statistics and schedule
            if result.get('success'):
                # Calculate next run time based on schedule
                from thoth.services.research_question_service import (
                    ResearchQuestionService,
                )  # noqa: I001

                next_run = ResearchQuestionService(self.config)._calculate_next_run(
                    frequency=question.get('schedule_frequency', 'daily'),
                    schedule_time=question.get('schedule_time'),
                    schedule_days_of_week=question.get('schedule_days_of_week'),
                )

                # Update question record
                await self.research_question_service.repository.update_question(
                    question_id=question_id,
                    last_run_at=datetime.now(),
                    next_run_at=next_run,
                )

                logger.info(
                    f'Updated question {question_id} schedule: next run at {next_run}'
                )

            # Log execution to discovery_execution_log
            await self._log_discovery_execution(
                question_id=question_id,
                success=result.get('success', False),
                articles_found=result.get('articles_found', 0),
                articles_matched=result.get('articles_matched', 0),
                execution_time=execution_time,
                error_message=result.get('error'),
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f'Discovery failed for question {question_id}: {e}', exc_info=True
            )

            # Log failed execution
            await self._log_discovery_execution(
                question_id=question_id,
                success=False,
                articles_found=0,
                articles_matched=0,
                execution_time=execution_time,
                error_message=str(e),
            )

            return {
                'success': False,
                'question_id': str(question_id),
                'error': str(e),
                'execution_time_seconds': execution_time,
            }

    async def _log_discovery_execution(
        self,
        question_id: str,
        success: bool,
        articles_found: int,
        articles_matched: int,
        execution_time: float,
        error_message: str = None,  # noqa: RUF013
    ) -> None:
        """
        Log discovery execution to PostgreSQL discovery_execution_log table.

        Args:
            question_id: Research question UUID
            success: Whether discovery succeeded
            articles_found: Number of articles found
            articles_matched: Number of articles matched
            execution_time: Execution time in seconds
            error_message: Error message if failed
        """
        try:
            import asyncpg

            db_url = (
                getattr(self.config.secrets, 'database_url', None)
                if hasattr(self.config, 'secrets')
                else None
            )
            if not db_url:
                logger.warning('DATABASE_URL not configured - skipping execution log')
                return

            conn = await asyncpg.connect(db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO discovery_execution_log (
                        question_id,
                        executed_at,
                        success,
                        articles_found,
                        articles_matched,
                        execution_time_seconds,
                        error_message
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    question_id,
                    datetime.now(),
                    success,
                    articles_found,
                    articles_matched,
                    execution_time,
                    error_message,
                )
                logger.debug(f'Logged discovery execution for question {question_id}')
            finally:
                await conn.close()

        except Exception as e:
            logger.error(f'Failed to log discovery execution: {e}', exc_info=True)
