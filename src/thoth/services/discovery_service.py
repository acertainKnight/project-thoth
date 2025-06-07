"""
Discovery service for managing article discovery sources.

This module consolidates all discovery-related operations that were previously
scattered across DiscoveryManager, Filter, and agent tools.
"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from thoth.discovery.api_sources import (
    ArxivAPISource,
    PubMedAPISource,
    CrossRefAPISource,
)
from thoth.discovery.web_scraper import WebScraper
from thoth.services.base import BaseService, ServiceError
from thoth.utilities.models import (
    DiscoveryResult,
    DiscoverySource,
    ScheduleConfig,
    ScrapedArticleMetadata,
)


class DiscoveryService(BaseService):
    """
    Service for managing article discovery from various sources.

    This service consolidates all discovery-related operations including:
    - Managing discovery sources (API and scrapers)
    - Running discovery operations
    - Coordinating with filtering
    - Managing discovery results
    - Scheduling automated discovery runs
    """

    def __init__(
        self,
        config=None,
        sources_dir: Path | None = None,
        results_dir: Path | None = None,
    ):
        """
        Initialize the DiscoveryService.

        Args:
            config: Optional configuration object
            sources_dir: Directory for storing source configurations
            results_dir: Directory for storing discovery results
        """
        super().__init__(config)
        self.sources_dir = Path(sources_dir or self.config.discovery_sources_dir)
        self.sources_dir.mkdir(parents=True, exist_ok=True)

        self.results_dir = Path(results_dir or self.config.discovery_results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Initialize API sources
        self.api_sources = {
            'arxiv': ArxivAPISource(),
            'pubmed': PubMedAPISource(),
            'crossref': CrossRefAPISource(),
        }

        # Initialize web scraper
        self.web_scraper = WebScraper()

        # Scheduler state
        self.scheduler_running = False
        self.scheduler_thread = None
        self.schedule_file = self.config.agent_storage_dir / 'discovery_schedule.json'
        self.schedule_state = self._load_schedule_state()

        # Reference to filter function (set externally)
        self.filter_func = None

        self._discovery_manager = None
        self._scheduler = None

    def initialize(self) -> None:
        """Initialize the discovery service."""
        self.logger.info('Discovery service initialized')

    def create_source(self, source: DiscoverySource) -> bool:
        """
        Create a new discovery source.

        Args:
            source: Discovery source configuration

        Returns:
            bool: True if successful

        Raises:
            ServiceError: If creation fails
        """
        try:
            self.validate_input(source=source)

            # Set timestamps
            now = datetime.now().isoformat()
            if not source.created_at:
                source.created_at = now
            source.updated_at = now

            # Save configuration
            source_file = self.sources_dir / f'{source.name}.json'
            if source_file.exists():
                raise ServiceError(f"Source '{source.name}' already exists")

            with open(source_file, 'w') as f:
                json.dump(source.model_dump(), f, indent=2)

            self.log_operation(
                'source_created', name=source.name, type=source.source_type
            )
            return True

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"creating source '{source.name}'")
            ) from e

    def get_source(self, name: str) -> DiscoverySource | None:
        """
        Get a discovery source by name.

        Args:
            name: Name of the source

        Returns:
            DiscoverySource: The source if found, None otherwise
        """
        try:
            source_file = self.sources_dir / f'{name}.json'
            if not source_file.exists():
                self.logger.debug(f"Source '{name}' not found")
                return None

            with open(source_file) as f:
                data = json.load(f)
                return DiscoverySource(**data)

        except Exception as e:
            self.logger.error(self.handle_error(e, f"loading source '{name}'"))
            return None

    def list_sources(self, active_only: bool = False) -> list[DiscoverySource]:
        """
        List all discovery sources.

        Args:
            active_only: If True, only return active sources

        Returns:
            list[DiscoverySource]: List of sources
        """
        sources = []
        for source_file in self.sources_dir.glob('*.json'):
            try:
                with open(source_file) as f:
                    data = json.load(f)
                    source = DiscoverySource(**data)

                    if not active_only or source.is_active:
                        sources.append(source)

            except Exception as e:
                self.logger.error(f'Failed to load source from {source_file}: {e}')

        return sources

    def update_source(self, source: DiscoverySource) -> bool:
        """
        Update an existing discovery source.

        Args:
            source: Updated source configuration

        Returns:
            bool: True if successful
        """
        try:
            source_file = self.sources_dir / f'{source.name}.json'
            if not source_file.exists():
                raise ServiceError(f"Source '{source.name}' does not exist")

            # Update timestamp
            source.updated_at = datetime.now().isoformat()

            # Save configuration
            with open(source_file, 'w') as f:
                json.dump(source.model_dump(), f, indent=2)

            self.log_operation('source_updated', name=source.name)
            return True

        except Exception as e:
            self.logger.error(self.handle_error(e, f"updating source '{source.name}'"))
            return False

    def delete_source(self, name: str) -> bool:
        """
        Delete a discovery source.

        Args:
            name: Name of the source to delete

        Returns:
            bool: True if successful
        """
        try:
            source_file = self.sources_dir / f'{name}.json'
            if source_file.exists():
                source_file.unlink()
                self.log_operation('source_deleted', name=name)
                return True
            return False

        except Exception as e:
            self.logger.error(self.handle_error(e, f"deleting source '{name}'"))
            return False

    def run_discovery(
        self,
        source_name: str | None = None,
        max_articles: int | None = None,
        filter_func: Any | None = None,
    ) -> DiscoveryResult:
        """
        Run discovery for one or all sources.

        Args:
            source_name: Specific source to run, or None for all active sources
            max_articles: Maximum articles to discover
            filter_func: Optional function to filter articles

        Returns:
            DiscoveryResult: Results of the discovery run
        """
        start_time = time.time()

        try:
            # Get sources to run
            if source_name:
                source = self.get_source(source_name)
                if not source:
                    raise ServiceError(f"Source '{source_name}' not found")
                sources = [source]
            else:
                sources = self.list_sources(active_only=True)

            if not sources:
                return DiscoveryResult(
                    source_name=source_name or 'all',
                    run_timestamp=datetime.now().isoformat(),
                    articles_found=0,
                    articles_filtered=0,
                    articles_downloaded=0,
                    execution_time_seconds=time.time() - start_time,
                )

            # Run discovery for each source
            total_found = 0
            total_filtered = 0
            total_downloaded = 0
            all_errors = []

            for source in sources:
                if not source.is_active:
                    continue

                try:
                    self.logger.info(f'Running discovery for source: {source.name}')

                    # Discover articles
                    articles = self._discover_from_source(source, max_articles)
                    total_found += len(articles)

                    # Filter articles if function provided
                    if filter_func and articles:
                        filtered, downloaded, errors = self._filter_articles(
                            articles, filter_func, source.query_filters
                        )
                        total_filtered += filtered
                        total_downloaded += downloaded
                        all_errors.extend(errors)

                    # Update last run timestamp
                    source.last_run = datetime.now().isoformat()
                    self.update_source(source)

                except Exception as e:
                    error_msg = f'Error in source {source.name}: {e}'
                    self.logger.error(error_msg)
                    all_errors.append(error_msg)

            # Create result
            result = DiscoveryResult(
                source_name=source_name or 'all',
                run_timestamp=datetime.now().isoformat(),
                articles_found=total_found,
                articles_filtered=total_filtered,
                articles_downloaded=total_downloaded,
                errors=all_errors,
                execution_time_seconds=time.time() - start_time,
            )

            # Save result
            self._save_result(result)

            self.log_operation(
                'discovery_completed',
                source=source_name or 'all',
                found=total_found,
                filtered=total_filtered,
                downloaded=total_downloaded,
            )

            return result

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'running discovery')) from e

    def _discover_from_source(
        self, source: DiscoverySource, max_articles: int | None = None
    ) -> list[ScrapedArticleMetadata]:
        """Discover articles from a specific source."""
        articles = []

        try:
            if source.source_type == 'api' and source.api_config:
                # Use API source
                source_type = source.api_config.get('source')
                if source_type in self.api_sources:
                    api_source = self.api_sources[source_type]
                    default_max = source.schedule_config.max_articles_per_run
                    articles = api_source.search(
                        source.api_config, max_articles or default_max
                    )
                else:
                    self.logger.error(f'Unknown API source type: {source_type}')

            elif source.source_type == 'scraper' and source.scraper_config:
                # Use web scraper
                articles = self.web_scraper.scrape(
                    source.scraper_config,
                    max_articles or source.schedule_config.max_articles_per_run,
                )

            else:
                self.logger.warning(f'Invalid source configuration for {source.name}')

        except Exception as e:
            self.logger.error(f'Failed to discover from source {source.name}: {e}')

        return articles

    def _filter_articles(
        self,
        articles: list[ScrapedArticleMetadata],
        filter_func: Any,
        query_filters: list[str],
    ) -> tuple[int, int, list[str]]:
        """Filter articles and process them."""
        filtered_count = 0
        downloaded_count = 0
        errors = []

        for article in articles:
            try:
                # Apply filter function
                result = filter_func(
                    metadata=article,
                    query_names=query_filters if query_filters else None,
                    download_pdf=True,
                )

                if result['decision'] == 'download':
                    filtered_count += 1
                    if result.get('pdf_downloaded'):
                        downloaded_count += 1
                    elif result.get('error_message'):
                        errors.append(
                            f"PDF download failed for '{article.title}': {result['error_message']}"
                        )

            except Exception as e:
                error_msg = f"Error processing article '{article.title}': {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        return filtered_count, downloaded_count, errors

    def _save_result(self, result: DiscoveryResult) -> None:
        """Save discovery result to file."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_file = (
                self.results_dir / f'discovery_{result.source_name}_{timestamp}.json'
            )

            with open(result_file, 'w') as f:
                json.dump(result.model_dump(), f, indent=2)

            self.logger.debug(f'Saved discovery result to: {result_file}')

        except Exception as e:
            self.logger.error(f'Failed to save discovery result: {e}')

    def get_statistics(self, days: int = 30) -> dict[str, Any]:
        """
        Get discovery statistics for the last N days.

        Args:
            days: Number of days to include

        Returns:
            dict[str, Any]: Discovery statistics
        """
        try:
            cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)

            stats = {
                'total_runs': 0,
                'total_articles_found': 0,
                'total_articles_filtered': 0,
                'total_articles_downloaded': 0,
                'total_errors': 0,
                'sources': {},
                'average_execution_time': 0.0,
            }

            total_execution_time = 0.0

            for result_file in self.results_dir.glob('discovery_*.json'):
                try:
                    # Check file modification time
                    if result_file.stat().st_mtime < cutoff_time:
                        continue

                    with open(result_file) as f:
                        result_data = json.load(f)

                    result = DiscoveryResult(**result_data)

                    # Update statistics
                    stats['total_runs'] += 1
                    stats['total_articles_found'] += result.articles_found
                    stats['total_articles_filtered'] += result.articles_filtered
                    stats['total_articles_downloaded'] += result.articles_downloaded
                    stats['total_errors'] += len(result.errors)
                    total_execution_time += result.execution_time_seconds

                    # Source-specific stats
                    source_name = result.source_name
                    if source_name not in stats['sources']:
                        stats['sources'][source_name] = {
                            'runs': 0,
                            'articles_found': 0,
                            'articles_filtered': 0,
                            'articles_downloaded': 0,
                            'errors': 0,
                        }

                    source_stats = stats['sources'][source_name]
                    source_stats['runs'] += 1
                    source_stats['articles_found'] += result.articles_found
                    source_stats['articles_filtered'] += result.articles_filtered
                    source_stats['articles_downloaded'] += result.articles_downloaded
                    source_stats['errors'] += len(result.errors)

                except Exception as e:
                    self.logger.error(
                        f'Error processing result file {result_file}: {e}'
                    )

            if stats['total_runs'] > 0:
                stats['average_execution_time'] = (
                    total_execution_time / stats['total_runs']
                )

            return stats

        except Exception as e:
            self.logger.error(self.handle_error(e, 'getting discovery statistics'))
            return {}

    def start_scheduler(self) -> None:
        """
        Start the discovery scheduler.

        Raises:
            ServiceError: If scheduler is already running.
        """
        if self.scheduler_running:
            raise ServiceError('Scheduler is already running')

        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True
        )
        self.scheduler_thread.start()

        self.logger.info('Discovery scheduler started')

    def stop_scheduler(self) -> None:
        """Stop the discovery scheduler."""
        if not self.scheduler_running:
            return

        self.scheduler_running = False

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5.0)

        self.logger.info('Discovery scheduler stopped')

    def get_schedule_status(self) -> dict[str, Any]:
        """
        Get the current status of all scheduled sources.

        Returns:
            dict[str, Any]: Schedule status information.
        """
        sources_status = []

        for source_name, schedule_info in self.schedule_state.items():
            source = self.get_source(source_name)

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
            'running': self.scheduler_running,
            'total_sources': len(self.schedule_state),
            'enabled_sources': sum(
                1 for s in self.schedule_state.values() if s.get('enabled', False)
            ),
            'sources': sources_status,
        }

    def _scheduler_loop(self) -> None:
        """Main scheduler loop that runs in a separate thread."""
        self.logger.info('Scheduler loop started')

        while self.scheduler_running:
            try:
                self._check_and_run_scheduled_sources()
                time.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f'Error in scheduler loop: {e}')
                time.sleep(60)

        self.logger.info('Scheduler loop stopped')

    def _check_and_run_scheduled_sources(self) -> None:
        """Check for sources that need to run and execute them."""
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
                    self.logger.info(
                        f'Running scheduled discovery for source: {source_name}'
                    )

                    # Run the source
                    max_articles = schedule_info.get('max_articles_per_run')
                    result = self.run_discovery(
                        source_name, max_articles, self.filter_func
                    )

                    # Update schedule state
                    schedule_info['last_run'] = current_time.isoformat()

                    # Calculate next run time
                    source = self.get_source(source_name)
                    if source and source.schedule_config:
                        schedule_info['next_run'] = self._calculate_next_run(
                            source.schedule_config
                        )

                    self.logger.info(
                        f'Scheduled discovery completed for {source_name}: '
                        f'{result.articles_found} found, {result.articles_downloaded} downloaded'
                    )

            except Exception as e:
                self.logger.error(f'Error running scheduled source {source_name}: {e}')

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
                self.logger.warning(
                    f'Invalid time_of_day format: {schedule.time_of_day}'
                )

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
        """Load schedule state from file."""
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file) as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f'Error loading schedule state: {e}')

        return {}

    def _save_schedule_state(self) -> None:
        """Save schedule state to file."""
        try:
            self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.schedule_file, 'w') as f:
                json.dump(self.schedule_state, f, indent=2)
        except Exception as e:
            self.logger.error(f'Error saving schedule state: {e}')
