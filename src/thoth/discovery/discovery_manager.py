"""
Discovery manager for orchestrating article discovery from various sources.

This module provides the main DiscoveryManager class that coordinates
article discovery from APIs and web scraping sources, applies filtering,
and integrates with the existing Thoth pipeline.
"""

import json  # noqa: I001
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.discovery.api_sources import (
    BioRxivAPISource,
    CrossRefAPISource,
    OpenAlexAPISource,
    PubMedAPISource,
)
from thoth.discovery.plugins import plugin_registry
from thoth.discovery.emulator_scraper import EmulatorScraper
from thoth.discovery.web_scraper import WebScraper
from thoth.config import config
from thoth.utilities.schemas import (
    DiscoveryResult,
    DiscoverySource,
    ResearchQuery,
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
    2. Running discovery from APIs, web scrapers, and browser recordings
    3. Applying filtering through the Filter
    4. Coordinating with the scheduling system
    """

    def __init__(
        self,
        sources_config_dir: str | Path | None = None,
        source_repo=None,
    ):
        """
        Initialize the Discovery Manager.

        Args:
            sources_config_dir: Directory containing discovery source configurations.
            source_repo: Optional AvailableSourceRepository for database access.
        """
        self.config = config
        self.source_repo = source_repo

        # Set up sources configuration directory
        self.sources_config_dir = Path(
            sources_config_dir or self.config.discovery_sources_dir
        )
        self.sources_config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize plugin registry for modern plugin-based sources
        self.plugin_registry = plugin_registry

        # Initialize legacy API sources (will be deprecated)
        self.api_sources = {
            'pubmed': PubMedAPISource(),
            'crossref': CrossRefAPISource(),
            'openalex': OpenAlexAPISource(),
            'biorxiv': BioRxivAPISource(),
        }

        # Initialize web scraper
        self.web_scraper = WebScraper()
        self.emulator_scraper = EmulatorScraper()

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

    async def get_source(self, source_name: str) -> DiscoverySource | None:
        """
        Get a discovery source configuration by name from database.

        Args:
            source_name: Name of the source to retrieve.

        Returns:
            DiscoverySource: The source configuration, or None if not found.
        """
        try:
            # Use repository if available
            if self.source_repo:
                source_record = await self.source_repo.get_by_name(source_name)
                if not source_record or not source_record.get('is_active'):
                    logger.debug(
                        f"Source '{source_name}' not found or inactive in database"
                    )
                    return None

                # Map database record to DiscoverySource model
                return DiscoverySource(
                    name=source_record['name'],
                    source_type='api',  # All current sources are API-based
                    description=source_record.get('description', ''),
                    is_active=source_record['is_active'],
                    schedule_config={
                        'interval_minutes': 1440,
                        'max_articles_per_run': 50,
                        'enabled': True,
                    },
                    api_config={
                        'source': source_record[
                            'name'
                        ],  # CRITICAL: Add source identifier
                        **source_record.get('config', {}),
                    },
                    scraper_config=None,
                    browser_recording=None,
                    query_filters=[],
                )

            # Fallback to JSON file (backward compatibility)
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
                    if articles:
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
        self,
        source: DiscoverySource,
        max_articles: int | None = None,
        question: dict[str, Any] | None = None,
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles from a specific source.

        Args:
            source: DiscoverySource configuration.
            max_articles: Maximum number of articles to retrieve.
            question: Research question with keywords, topics, and authors.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        articles = []

        try:
            if source.source_type == 'api' and source.api_config:
                articles = self._discover_from_api(
                    source.api_config, max_articles, question
                )
            elif source.source_type == 'scraper' and source.scraper_config:
                articles = self._discover_from_scraper(
                    source.scraper_config, max_articles
                )
            elif (
                source.source_type == 'emulator'
                and source.scraper_config
                and source.browser_recording
            ):
                articles = self.emulator_scraper.scrape(
                    source.browser_recording,
                    source.scraper_config,
                    max_articles or 50,
                )
            else:
                logger.warning(f'Invalid source configuration for {source.name}')

        except Exception as e:
            logger.error(f'Failed to discover from source {source.name}: {e}')

        return articles

    def _discover_from_api(
        self,
        api_config: dict[str, Any],
        max_articles: int | None = None,
        question: dict[str, Any] | None = None,
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles from API sources.

        Args:
            api_config: API configuration dictionary.
            max_articles: Maximum number of articles to retrieve.
            question: Research question with keywords, topics, and authors.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        source_type = api_config.get('source')

        # Use the source's configured max_articles_per_run
        # if no explicit max_articles provided
        default_max = api_config.get('schedule_config', {}).get(
            'max_articles_per_run', 50
        )

        # Check if this source has a modern plugin implementation
        if self.plugin_registry.get(source_type):
            return self._discover_from_plugin(
                source_type, api_config, max_articles or default_max, question
            )

        # Fall back to legacy API sources
        if source_type not in self.api_sources:
            logger.error(f'Unknown API source type: {source_type}')
            return []

        api_source = self.api_sources[source_type]

        # Merge research question data into API config
        enhanced_config = api_config.copy()
        if question:
            # Add keywords from research question
            if question.get('keywords'):
                existing_keywords = enhanced_config.get('keywords', [])
                enhanced_config['keywords'] = list(
                    set(existing_keywords + question['keywords'])
                )

            # Add topics/categories from research question
            if question.get('topics'):
                existing_categories = enhanced_config.get('categories', [])
                enhanced_config['categories'] = list(
                    set(existing_categories + question['topics'])
                )

            # Add preferred authors from research question
            if question.get('authors'):
                enhanced_config['preferred_authors'] = question['authors']

            # Build optimized search query for ArXiv API
            # ArXiv needs explicit search_query parameter with proper syntax
            if source_type == 'arxiv' and (
                question.get('keywords') or question.get('topics')
            ):
                query_parts = []

                # Add category filters (topics -> ArXiv categories)
                if question.get('topics'):
                    # Limit to top 3 topics to avoid overly restrictive queries
                    top_topics = question['topics'][:3]
                    cat_queries = [f'cat:{topic}' for topic in top_topics]
                    if cat_queries:
                        query_parts.append(f'({" OR ".join(cat_queries)})')

                # Add keyword searches (search in title and abstract)
                if question.get('keywords'):
                    # Limit to top 5 keywords for focused results
                    top_keywords = question['keywords'][:5]
                    keyword_queries = []
                    for keyword in top_keywords:
                        # Search in title OR abstract for each keyword
                        keyword_queries.append(f'(ti:"{keyword}" OR abs:"{keyword}")')
                    if keyword_queries:
                        query_parts.append(f'({" OR ".join(keyword_queries)})')

                # Combine with AND for more focused results
                if query_parts:
                    search_query = ' AND '.join(query_parts)
                    enhanced_config['search_query'] = search_query
                    logger.info(f'Built ArXiv search query: {search_query}')

            # Add date filters from research question
            if question:
                if question.get('date_filter_start'):
                    enhanced_config['start_date'] = str(question['date_filter_start'])
                if question.get('date_filter_end'):
                    enhanced_config['end_date'] = str(question['date_filter_end'])

            logger.info(
                f'Enhanced API config with research question data: '
                f'keywords={enhanced_config.get("keywords", [])}, '
                f'categories={enhanced_config.get("categories", [])}, '
                f'authors={enhanced_config.get("preferred_authors", [])}, '
                f'search_query={enhanced_config.get("search_query", "N/A")}, '
                f'date_range={enhanced_config.get("start_date", "N/A")} to {enhanced_config.get("end_date", "present")}'
            )

        try:
            return api_source.search(enhanced_config, max_articles or default_max)
        except Exception as e:
            logger.error(f'API search failed for {source_type}: {e}')
            return []

    def _discover_from_plugin(
        self,
        source_type: str,
        api_config: dict[str, Any],
        max_articles: int,
        question: dict | None = None,
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles using modern plugin architecture.

        Args:
            source_type: Plugin type (e.g., 'arxiv').
            api_config: API configuration dictionary.
            max_articles: Maximum number of articles to retrieve.
            question: Research question with keywords, topics, and authors.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        try:
            # Create plugin instance with config
            plugin = self.plugin_registry.create(source_type, config=api_config)

            # Build ResearchQuery from question data
            if question:
                keywords = question.get('keywords', [])
                # Extract search query if present
                if api_config.get('search_query'):
                    # Plugin will use the pre-built search query from its config
                    pass
            else:
                keywords = api_config.get('keywords', [])

            # Create ResearchQuery for plugin
            research_query = ResearchQuery(
                name=api_config.get('name', source_type),
                description=api_config.get(
                    'description', f'Discovery from {source_type}'
                ),
                research_question=question.get('question', '') if question else '',
                keywords=keywords,
                required_topics=question.get('topics', []) if question else [],
            )

            logger.info(
                f'Using plugin {source_type} with keywords={keywords}, '
                f'max_results={max_articles}'
            )

            # Call plugin's discover method
            return plugin.discover(research_query, max_articles)

        except Exception as e:
            logger.error(f'Plugin discovery failed for {source_type}: {e}')
            return []

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
