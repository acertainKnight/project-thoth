"""
Discovery scheduler for managing automated article discovery.

This module provides scheduling functionality for running discovery
sources on configurable cadences and managing the discovery workflow.
"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.utilities.config import get_config
from thoth.utilities.models import DiscoverySource, ScheduleConfig


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
    ):
        """
        Initialize the Discovery Scheduler.

        Args:
            discovery_manager: DiscoveryManager instance for running discovery.
            schedule_file: Path to file for storing schedule state.
        """
        self.config = get_config()
        self.discovery_manager = discovery_manager or DiscoveryManager()

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
            result = self.discovery_manager.run_discovery(source_name, max_articles)

            # Update schedule state
            if source_name in self.schedule_state:
                self.schedule_state[source_name]['last_run'] = (
                    datetime.now().isoformat()
                )
                self._save_schedule_state()

            return result.model_dump()

        except Exception as e:
            logger.error(f'Error running source {source_name}: {e}')
            return {'error': str(e)}

    def _scheduler_loop(self) -> None:
        """
        Main scheduler loop that runs in a separate thread.
        """
        logger.info('Scheduler loop started')

        while self.running:
            try:
                self._check_and_run_scheduled_sources()

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
                        source_name, max_articles
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
        Load schedule state from file.

        Returns:
            dict[str, Any]: Schedule state dictionary.
        """
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f'Error loading schedule state: {e}')

        return {}

    def _save_schedule_state(self) -> None:
        """
        Save schedule state to file.
        """
        try:
            with open(self.schedule_file, 'w') as f:
                json.dump(self.schedule_state, f, indent=2)
        except Exception as e:
            logger.error(f'Error saving schedule state: {e}')

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
