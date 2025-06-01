"""
Discovery manager for orchestrating article discovery from various sources.

This module provides the main DiscoveryManager class that coordinates
article discovery from APIs and web scraping sources, applies filtering,
and integrates with the existing Thoth pipeline.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.discovery.api_sources import ArxivAPISource, PubMedAPISource
from thoth.discovery.web_scraper import WebScraper
from thoth.ingestion.filter import Filter
from thoth.utilities.config import get_config
from thoth.utilities.models import (
    DiscoveryResult,
    DiscoverySource,
    ScrapedArticleMetadata,
)


class DiscoveryManagerError(Exception):
    """Exception raised for errors in the discovery manager."""

    pass


class DiscoveryManager:
    """
    Main manager for article discovery from various sources.

    This class orchestrates the discovery process by:
    1. Managing discovery source configurations
    2. Running discovery from APIs and web scrapers
    3. Applying filtering through the Filter
    4. Coordinating with the scheduling system
    """

    def __init__(
        self,
        filter: Filter | None = None,
        sources_config_dir: str | Path | None = None,
    ):
        """
        Initialize the Discovery Manager.

        Args:
            filter: Filter instance for filtering articles.
            sources_config_dir: Directory containing discovery source configurations.
        """
        self.config = get_config()
        self.filter = filter

        # Set up sources configuration directory
        self.sources_config_dir = Path(
            sources_config_dir or self.config.discovery_sources_dir
        )
        self.sources_config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize API sources
        self.api_sources = {
            'arxiv': ArxivAPISource(),
            'pubmed': PubMedAPISource(),
        }

        # Initialize web scraper
        self.web_scraper = WebScraper()

        # Results storage
        self.results_dir = self.config.discovery_results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f'Discovery manager initialized with sources dir: {self.sources_config_dir}'
        )

    def create_source(self, source: DiscoverySource) -> None:
        """
        Create a new discovery source configuration.

        Args:
            source: DiscoverySource configuration to create.

        Raises:
            DiscoveryManagerError: If source creation fails.

        Example:
            >>> manager = DiscoveryManager()
            >>> source = DiscoverySource(
            ...     name='arxiv_ml',
            ...     source_type='api',
            ...     description='ArXiv machine learning papers',
            ...     api_config={'source': 'arxiv', 'categories': ['cs.LG']},
            ... )
            >>> manager.create_source(source)
        """
        try:
            source_file = self.sources_config_dir / f'{source.name}.json'

            if source_file.exists():
                raise DiscoveryManagerError(f'Source {source.name} already exists')

            # Set timestamps
            now = datetime.now().isoformat()
            source.created_at = now
            source.updated_at = now

            # Save configuration
            with open(source_file, 'w') as f:
                json.dump(source.model_dump(), f, indent=2)

            logger.info(f'Created discovery source: {source.name}')

        except Exception as e:
            raise DiscoveryManagerError(
                f'Failed to create source {source.name}: {e}'
            ) from e

    def update_source(self, source: DiscoverySource) -> None:
        """
        Update an existing discovery source configuration.

        Args:
            source: Updated DiscoverySource configuration.

        Raises:
            DiscoveryManagerError: If source update fails.
        """
        try:
            source_file = self.sources_config_dir / f'{source.name}.json'

            if not source_file.exists():
                raise DiscoveryManagerError(f'Source {source.name} does not exist')

            # Update timestamp
            source.updated_at = datetime.now().isoformat()

            # Save configuration
            with open(source_file, 'w') as f:
                json.dump(source.model_dump(), f, indent=2)

            logger.info(f'Updated discovery source: {source.name}')

        except Exception as e:
            raise DiscoveryManagerError(
                f'Failed to update source {source.name}: {e}'
            ) from e

    def delete_source(self, source_name: str) -> None:
        """
        Delete a discovery source configuration.

        Args:
            source_name: Name of the source to delete.

        Raises:
            DiscoveryManagerError: If source deletion fails.
        """
        try:
            source_file = self.sources_config_dir / f'{source_name}.json'

            if not source_file.exists():
                raise DiscoveryManagerError(f'Source {source_name} does not exist')

            source_file.unlink()
            logger.info(f'Deleted discovery source: {source_name}')

        except Exception as e:
            raise DiscoveryManagerError(
                f'Failed to delete source {source_name}: {e}'
            ) from e

    def get_source(self, source_name: str) -> DiscoverySource | None:
        """
        Get a discovery source configuration by name.

        Args:
            source_name: Name of the source to retrieve.

        Returns:
            DiscoverySource: The source configuration, or None if not found.
        """
        try:
            source_file = self.sources_config_dir / f'{source_name}.json'

            if not source_file.exists():
                return None

            with open(source_file) as f:
                source_data = json.load(f)

            return DiscoverySource(**source_data)

        except Exception as e:
            logger.error(f'Failed to load source {source_name}: {e}')
            return None

    def list_sources(self, active_only: bool = False) -> list[DiscoverySource]:
        """
        List all discovery source configurations.

        Args:
            active_only: If True, only return active sources.

        Returns:
            list[DiscoverySource]: List of discovery source configurations.
        """
        sources = []

        for source_file in self.sources_config_dir.glob('*.json'):
            try:
                with open(source_file) as f:
                    source_data = json.load(f)

                source = DiscoverySource(**source_data)

                if not active_only or source.is_active:
                    sources.append(source)

            except Exception as e:
                logger.error(f'Failed to load source from {source_file}: {e}')

        return sources

    def run_discovery(
        self,
        source_name: str | None = None,
        max_articles: int | None = None,
    ) -> DiscoveryResult:
        """
        Run discovery for a specific source or all active sources.

        Args:
            source_name: Name of specific source to run, or None for all active sources.
            max_articles: Maximum number of articles to process.

        Returns:
            DiscoveryResult: Results of the discovery run.

        Raises:
            DiscoveryManagerError: If discovery fails.

        Example:
            >>> manager = DiscoveryManager()
            >>> result = manager.run_discovery('arxiv_ml', max_articles=50)
            >>> print(f'Found {result.articles_found} articles')
        """
        start_time = time.time()

        try:
            if source_name:
                sources = [self.get_source(source_name)]
                if not sources[0]:
                    raise DiscoveryManagerError(f'Source {source_name} not found')
            else:
                sources = self.list_sources(active_only=True)

            if not sources:
                logger.warning('No active sources found for discovery')
                return DiscoveryResult(
                    source_name=source_name or 'all',
                    run_timestamp=datetime.now().isoformat(),
                    articles_found=0,
                    articles_filtered=0,
                    articles_downloaded=0,
                    execution_time_seconds=time.time() - start_time,
                )

            total_found = 0
            total_filtered = 0
            total_downloaded = 0
            all_errors = []

            for source in sources:
                if not source.is_active:
                    continue

                try:
                    logger.info(f'Running discovery for source: {source.name}')

                    # Get articles from source
                    articles = self._discover_from_source(source, max_articles)
                    total_found += len(articles)

                    logger.info(f'Found {len(articles)} articles from {source.name}')

                    # Filter and process articles
                    if self.filter and articles:
                        filtered_count, downloaded_count, errors = (
                            self._filter_and_process_articles(
                                articles, source.query_filters
                            )
                        )
                        total_filtered += filtered_count
                        total_downloaded += downloaded_count
                        all_errors.extend(errors)

                    # Update last run timestamp
                    source.last_run = datetime.now().isoformat()
                    self.update_source(source)

                except Exception as e:
                    error_msg = f'Error in source {source.name}: {e}'
                    logger.error(error_msg)
                    all_errors.append(error_msg)

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
            self._save_discovery_result(result)

            logger.info(
                f'Discovery completed: {total_found} found, '
                f'{total_filtered} filtered, {total_downloaded} downloaded'
            )

            return result

        except Exception as e:
            raise DiscoveryManagerError(f'Discovery failed: {e}') from e

    def _discover_from_source(
        self, source: DiscoverySource, max_articles: int | None = None
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles from a specific source.

        Args:
            source: DiscoverySource configuration.
            max_articles: Maximum number of articles to retrieve.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        articles = []

        try:
            if source.source_type == 'api' and source.api_config:
                articles = self._discover_from_api(source.api_config, max_articles)
            elif source.source_type == 'scraper' and source.scraper_config:
                articles = self._discover_from_scraper(
                    source.scraper_config, max_articles
                )
            else:
                logger.warning(f'Invalid source configuration for {source.name}')

        except Exception as e:
            logger.error(f'Failed to discover from source {source.name}: {e}')

        return articles

    def _discover_from_api(
        self, api_config: dict[str, Any], max_articles: int | None = None
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles from API sources.

        Args:
            api_config: API configuration dictionary.
            max_articles: Maximum number of articles to retrieve.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        source_type = api_config.get('source')

        if source_type not in self.api_sources:
            logger.error(f'Unknown API source type: {source_type}')
            return []

        api_source = self.api_sources[source_type]
        # Use the source's configured max_articles_per_run
        # if no explicit max_articles provided
        default_max = api_config.get('schedule_config', {}).get(
            'max_articles_per_run', 50
        )
        return api_source.search(api_config, max_articles or default_max)

    def _discover_from_scraper(
        self, scraper_config, max_articles: int | None = None
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles from web scraping.

        Args:
            scraper_config: Scraper configuration.
            max_articles: Maximum number of articles to retrieve.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        return self.web_scraper.scrape(scraper_config, max_articles or 50)

    def _filter_and_process_articles(
        self,
        articles: list[ScrapedArticleMetadata],
        query_filters: list[str],
    ) -> tuple[int, int, list[str]]:
        """
        Filter articles and download approved PDFs.

        Args:
            articles: List of articles to filter.
            query_filters: List of query names to filter against.

        Returns:
            tuple[int, int, list[str]]: (filtered_count, downloaded_count, errors)
        """
        filtered_count = 0
        downloaded_count = 0
        errors = []

        for article in articles:
            try:
                # Process through filter
                result = self.filter.process_article(
                    metadata=article,
                    query_names=query_filters if query_filters else None,
                    download_pdf=True,
                )

                if result['decision'] == 'download':
                    filtered_count += 1
                    if result['pdf_downloaded']:
                        downloaded_count += 1
                    elif result['error_message']:
                        errors.append(
                            f"PDF download failed for '{article.title}': {result['error_message']}"
                        )

            except Exception as e:
                error_msg = f"Error processing article '{article.title}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return filtered_count, downloaded_count, errors

    def _save_discovery_result(self, result: DiscoveryResult) -> None:
        """
        Save discovery result to file.

        Args:
            result: DiscoveryResult to save.
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_file = (
                self.results_dir / f'discovery_{result.source_name}_{timestamp}.json'
            )

            with open(result_file, 'w') as f:
                json.dump(result.model_dump(), f, indent=2)

            logger.debug(f'Saved discovery result to: {result_file}')

        except Exception as e:
            logger.error(f'Failed to save discovery result: {e}')

    def get_discovery_statistics(self, days: int = 30) -> dict[str, Any]:
        """
        Get discovery statistics for the last N days.

        Args:
            days: Number of days to include in statistics.

        Returns:
            dict[str, Any]: Discovery statistics.

        Example:
            >>> manager = DiscoveryManager()
            >>> stats = manager.get_discovery_statistics(7)
            >>> print(f'Total articles found: {stats["total_articles_found"]}')
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
                    logger.error(f'Error processing result file {result_file}: {e}')

            if stats['total_runs'] > 0:
                stats['average_execution_time'] = (
                    total_execution_time / stats['total_runs']
                )

            return stats

        except Exception as e:
            logger.error(f'Failed to get discovery statistics: {e}')
            return {}
