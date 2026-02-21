"""
Discovery service for managing article discovery sources.

This module consolidates all discovery-related operations that were previously
scattered across DiscoveryManager, Filter, and agent tools.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from thoth.discovery.api_sources import (
    BioRxivAPISource,
    CrossRefAPISource,
    OpenAlexAPISource,
    PubMedAPISource,
)
from thoth.discovery.emulator_scraper import EmulatorScraper
from thoth.discovery.plugins import ArxivPlugin, plugin_registry
from thoth.discovery.plugins.base import DiscoveryPluginRegistry
from thoth.discovery.web_scraper import WebScraper
from thoth.services.article_service import ArticleService
from thoth.services.base import BaseService, ServiceError
from thoth.services.pdf_locator_service import PdfLocatorService
from thoth.utilities.schemas import (
    DiscoveryResult,
    DiscoverySource,
    ResearchQuery,
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
        article_service: ArticleService | None = None,
    ):
        """
        Initialize the DiscoveryService.

        Args:
            config: Optional configuration object
            sources_dir: Directory for storing source configurations
            results_dir: Directory for storing discovery results
            article_service: Optional ArticleService instance
        """
        super().__init__(config)
        self._default_sources_dir = Path(
            sources_dir or self.config.discovery_sources_dir
        )
        self._default_sources_dir.mkdir(parents=True, exist_ok=True)

        self._default_results_dir = Path(
            results_dir or self.config.discovery_results_dir
        )
        self._default_results_dir.mkdir(parents=True, exist_ok=True)

        # Initialize API sources and plugin registry
        self.api_sources = {
            'pubmed': PubMedAPISource(),
            'crossref': CrossRefAPISource(),
            'openalex': OpenAlexAPISource(),
            'biorxiv': BioRxivAPISource(),
        }
        self.plugin_registry: DiscoveryPluginRegistry = plugin_registry
        if 'arxiv' not in self.plugin_registry.list_plugins():
            self.plugin_registry.register('arxiv', ArxivPlugin)

        # Initialize web scraper
        self.web_scraper = WebScraper()
        self.emulator_scraper = EmulatorScraper()

        # Reference to filter function (set externally)
        self.article_service = article_service or ArticleService(config=self.config)

        # Initialize PDF locator service
        self.pdf_locator = PdfLocatorService(config=self.config)

        self._discovery_manager = None

    @property
    def sources_dir(self) -> Path:
        """Discovery sources dir, scoped to current user when available."""
        up = self._get_user_paths()
        return up.discovery_sources_dir if up else self._default_sources_dir

    @property
    def results_dir(self) -> Path:
        """Discovery results dir, scoped to current user when available."""
        up = self._get_user_paths()
        return up.discovery_results_dir if up else self._default_results_dir

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
    ) -> DiscoveryResult:
        """
        Run discovery for one or all sources.

        Args:
            source_name: Specific source to run, or None for all active sources
            max_articles: Maximum articles to discover

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
                    if articles:
                        filtered, downloaded, errors = self._filter_articles(
                            articles, source.query_filters
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
                source_type = source.api_config.get('source')
                if self.plugin_registry.get(source_type):
                    plugin = self.plugin_registry.create(
                        source_type, config=source.api_config
                    )
                    dummy_query = ResearchQuery(
                        name=source.name,
                        description=source.description,
                        research_question=source.description,
                        keywords=source.api_config.get('keywords', []),
                    )
                    default_max = source.schedule_config.max_articles_per_run
                    articles = plugin.discover(dummy_query, max_articles or default_max)
                elif source_type in self.api_sources:
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

            elif (
                source.source_type == 'emulator'
                and source.browser_recording
                and source.scraper_config
            ):
                articles = self.emulator_scraper.scrape(
                    recording=source.browser_recording,
                    config=source.scraper_config,
                    max_articles=max_articles
                    or source.schedule_config.max_articles_per_run,
                )
            else:
                self.logger.warning(f'Invalid source configuration for {source.name}')

        except Exception as e:
            self.logger.error(f'Failed to discover from source {source.name}: {e}')

        return articles

    def _filter_articles(
        self,
        articles: list[ScrapedArticleMetadata],
        query_filters: list[str],
    ) -> tuple[int, int, list[str]]:
        """Filter articles and process them."""
        filtered_count = 0
        downloaded_count = 0
        errors = []

        queries = []
        for query_name in query_filters:
            query = self.article_service.get_query(query_name)
            if query:
                queries.append(query)

        for article in articles:
            try:
                evaluation = self.article_service.evaluate_for_download(
                    article, queries
                )
                if evaluation.should_download:
                    filtered_count += 1
                    pdf_path = self._download_pdf(article)
                    if pdf_path:
                        downloaded_count += 1
                    else:
                        errors.append(f"PDF download failed for '{article.title}'")
            except Exception as e:
                error_msg = f"Error processing article '{article.title}': {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        return filtered_count, downloaded_count, errors

    def _download_pdf(self, metadata: ScrapedArticleMetadata) -> str | None:
        """Download PDF for an article."""
        pdf_url = metadata.pdf_url
        pdf_source = None
        pdf_licence = None
        is_oa = True

        # If no PDF URL, try to locate one
        if not pdf_url:
            self.logger.info(
                f'No PDF URL available for article: {metadata.title}, attempting to locate...'
            )

            pdf_location = self.pdf_locator.locate(
                doi=metadata.doi, arxiv_id=metadata.arxiv_id
            )

            if pdf_location:
                pdf_url = pdf_location.url
                pdf_source = pdf_location.source
                pdf_licence = pdf_location.licence
                is_oa = pdf_location.is_oa

                # Update metadata with located PDF info
                metadata.pdf_url = pdf_url
                if hasattr(metadata, 'oa_source'):
                    metadata.oa_source = pdf_source
                if hasattr(metadata, 'licence'):
                    metadata.licence = pdf_licence
                if hasattr(metadata, 'is_oa'):
                    metadata.is_oa = is_oa

                self.logger.info(f'PDF located via {pdf_source}: {pdf_url}')
            else:
                self.logger.warning(
                    f'Could not locate PDF for article: {metadata.title}'
                )
                return None

        try:
            # Create safe filename
            safe_title = ''.join(
                c for c in metadata.title if c.isalnum() or c in ' -_.'
            ).strip()
            safe_title = safe_title.replace(' ', '_')[:100]

            if metadata.doi:
                safe_title += f'_doi_{metadata.doi.replace("/", "_")}'
            elif metadata.arxiv_id:
                safe_title += f'_arxiv_{metadata.arxiv_id}'

            pdf_filename = f'{safe_title}.pdf'
            up = self._get_user_paths()
            _pdf_dir = up.pdf_dir if up else self.config.pdf_dir
            pdf_path = _pdf_dir / pdf_filename

            # Ensure unique filename
            counter = 1
            while pdf_path.exists():
                name_part = pdf_filename.rsplit('.', 1)[0]
                pdf_path = _pdf_dir / f'{name_part}_{counter}.pdf'
                counter += 1

            # Download the PDF using httpx streaming
            self.logger.info(f'Downloading PDF from: {pdf_url}')
            with httpx.stream(
                'GET', pdf_url, timeout=30, follow_redirects=True
            ) as response:
                response.raise_for_status()

                with open(pdf_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            self.logger.info(f'PDF downloaded successfully: {pdf_path}')
            return str(pdf_path)

        except Exception as e:
            self.logger.error(f'Failed to download PDF for {metadata.title}: {e}')
            return None

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

    def health_check(self) -> dict[str, str]:
        """Basic health status for the DiscoveryService."""
        return super().health_check()
