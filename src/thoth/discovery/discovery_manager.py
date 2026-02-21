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
        from thoth.mcp.auth import (
            get_current_user_paths,  # local import to avoid cycles
        )

        user_paths = get_current_user_paths()

        # Set up sources configuration directory
        default_sources_dir = (
            user_paths.discovery_sources_dir
            if user_paths
            else self.config.discovery_sources_dir
        )
        self.sources_config_dir = Path(sources_config_dir or default_sources_dir)
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
        self.results_dir = (
            user_paths.discovery_results_dir
            if user_paths
            else self.config.discovery_results_dir
        )
        self.results_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f'Discovery manager initialized with sources dir: {self.sources_config_dir}'
        )

    def health_check(self) -> dict[str, str]:
        """Return basic health status."""
        return {
            'status': 'healthy',
            'service': self.__class__.__name__,
        }

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
                db_source_type = source_record.get('source_type', 'api')

                # capabilities and config can come back as JSON strings from asyncpg
                raw_caps = source_record.get('capabilities') or {}
                if isinstance(raw_caps, str):
                    raw_caps = json.loads(raw_caps)
                raw_config = source_record.get('config') or {}
                if isinstance(raw_config, str):
                    raw_config = json.loads(raw_config)

                # Browser workflow sources need workflow_id from capabilities
                if db_source_type == 'browser_workflow':
                    return DiscoverySource(
                        name=source_record['name'],
                        source_type='browser_workflow',
                        description=source_record.get('description', ''),
                        is_active=source_record['is_active'],
                        schedule_config={
                            'interval_minutes': 1440,
                            'max_articles_per_run': 50,
                            'enabled': True,
                        },
                        api_config={
                            'source': 'browser_workflow',
                            'workflow_id': str(raw_caps.get('workflow_id', '')),
                            **raw_config,
                        },
                        scraper_config=None,
                        browser_recording=None,
                        query_filters=[],
                    )

                return DiscoverySource(
                    name=source_record['name'],
                    source_type='api',
                    description=source_record.get('description', ''),
                    is_active=source_record['is_active'],
                    schedule_config={
                        'interval_minutes': 1440,
                        'max_articles_per_run': 50,
                        'enabled': True,
                    },
                    api_config={
                        'source': source_record['name'],
                        **raw_config,
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

            # Collect all articles from all sources
            all_articles = []
            all_errors = []

            for source in sources:
                if not source.is_active:
                    continue

                try:
                    logger.info(f'Running discovery for source: {source.name}')

                    # Get articles from source
                    articles = self._discover_from_source(source, max_articles)
                    all_articles.extend(articles)

                    logger.info(f'Found {len(articles)} articles from {source.name}')

                    # Update last run timestamp
                    source.last_run = datetime.now().isoformat()
                    self.update_source(source)

                except Exception as e:
                    error_msg = f'Error in source {source.name}: {e}'
                    logger.error(error_msg)
                    all_errors.append(error_msg)

            # Deduplicate and merge articles from all sources
            total_found = len(all_articles)
            unique_articles = self._deduplicate_articles(all_articles)
            duplicates_removed = total_found - len(unique_articles)

            if duplicates_removed > 0:
                logger.info(
                    f'Deduplication: {total_found} articles → {len(unique_articles)} unique '
                    f'({duplicates_removed} duplicates merged)'
                )

            # Filter and process unique articles
            total_filtered = 0
            total_downloaded = 0

            if unique_articles:
                # Get combined query filters from all sources
                combined_filters = []
                for source in sources:
                    if source.is_active and source.query_filters:
                        combined_filters.extend(source.query_filters)

                filtered_count, downloaded_count, errors = (
                    self._filter_and_process_articles(
                        unique_articles, list(set(combined_filters))
                    )
                )
                total_filtered = filtered_count
                total_downloaded = downloaded_count
                all_errors.extend(errors)

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
                f'{len(unique_articles)} unique (after deduplication), '
                f'{total_filtered} filtered, {total_downloaded} downloaded'
            )

            return result

        except Exception as e:
            raise DiscoveryManagerError(f'Discovery failed: {e}') from e

    def _deduplicate_articles(
        self, articles: list[ScrapedArticleMetadata]
    ) -> list[ScrapedArticleMetadata]:
        """
        Deduplicate articles and merge metadata from multiple sources.

        Uses multiple matching strategies with cross-referencing:
        1. ArXiv ID (prioritized - most common in ML/AI)
        2. DOI
        3. Normalized title + first author (fallback)

        Args:
            articles: List of articles potentially containing duplicates.

        Returns:
            list[ScrapedArticleMetadata]: Deduplicated list with merged metadata.
        """
        if not articles:
            return []

        # Use multiple indexes for different ID types
        arxiv_index = {}  # arxiv_id -> article
        doi_index = {}  # doi -> article
        title_index = {}  # title+author -> article

        for article in articles:
            # Generate all possible keys for this article
            arxiv_key = None
            doi_key = None
            title_key = None

            if article.arxiv_id:
                # Normalize ArXiv ID (remove version)
                arxiv_id = article.arxiv_id.strip().lower()
                if 'v' in arxiv_id:
                    arxiv_id = arxiv_id.split('v')[0]
                arxiv_key = arxiv_id

            if article.doi:
                doi_key = article.doi.strip().lower()

            # Always generate title key as fallback
            title_key = self._generate_title_key(article)

            # Check if we've seen this article before (check all indexes)
            existing = None

            # Priority 1: Check ArXiv ID
            if arxiv_key and arxiv_key in arxiv_index:
                existing = arxiv_index[arxiv_key]

            # Priority 2: Check DOI
            elif doi_key and doi_key in doi_index:
                existing = doi_index[doi_key]
                # Also add to arxiv_index if this article has ArXiv ID
                if arxiv_key:
                    arxiv_index[arxiv_key] = existing

            # Priority 3: Check title
            elif title_key in title_index:
                existing = title_index[title_key]
                # Update other indexes
                if arxiv_key:
                    arxiv_index[arxiv_key] = existing
                if doi_key:
                    doi_index[doi_key] = existing

            if existing:
                # Duplicate found - merge and update in all indexes
                merged = self._merge_article_metadata(existing, article)

                # Update all relevant indexes with merged version
                if arxiv_key:
                    arxiv_index[arxiv_key] = merged
                if doi_key:
                    doi_index[doi_key] = merged
                title_index[title_key] = merged
            else:
                # New article - add to all relevant indexes
                if arxiv_key:
                    arxiv_index[arxiv_key] = article
                if doi_key:
                    doi_index[doi_key] = article
                title_index[title_key] = article

        # Return unique articles (use title_index as it has everything)
        seen_ids = set()
        unique = []
        for article in title_index.values():
            article_id = id(article)
            if article_id not in seen_ids:
                seen_ids.add(article_id)
                unique.append(article)

        return unique

    def _generate_title_key(self, article: ScrapedArticleMetadata) -> str:
        """Generate title+author key for fallback matching.

        Args:
            article: Article to generate key for.

        Returns:
            str: Title+author key.
        """
        title = self._normalize_title(article.title)
        first_author = ''
        if article.authors:
            first_author = self._normalize_author(article.authors[0])

        return f'{title}:{first_author}'

    def _normalize_title(self, title: str) -> str:
        """
        Normalize title for comparison.

        Args:
            title: Original title.

        Returns:
            str: Normalized title.
        """
        import re

        # Convert to lowercase
        title = title.lower()

        # Remove punctuation
        title = re.sub(r'[^\w\s]', '', title)

        # Remove extra whitespace
        title = ' '.join(title.split())

        return title

    def _normalize_author(self, author: str) -> str:
        """
        Normalize author name for comparison.

        Args:
            author: Original author name.

        Returns:
            str: Normalized author name.
        """
        # Convert to lowercase and remove extra spaces
        author = ' '.join(author.lower().split())
        return author

    def _merge_article_metadata(
        self,
        existing: ScrapedArticleMetadata,
        new: ScrapedArticleMetadata,
    ) -> ScrapedArticleMetadata:
        """
        Merge metadata from two versions of the same article.

        Strategy: Keep the most complete/detailed version of each field.

        Args:
            existing: Existing article metadata.
            new: New article metadata to merge.

        Returns:
            ScrapedArticleMetadata: Merged article with best fields from both.
        """
        # Convert to dicts for easier manipulation
        existing_dict = existing.model_dump()
        new_dict = new.model_dump()
        merged = existing_dict.copy()

        # Merge strategy for each field type

        # Title: Keep longer one (usually more complete)
        if len(new_dict.get('title', '')) > len(existing_dict.get('title', '')):
            merged['title'] = new_dict['title']

        # Authors: Keep longer list
        if len(new_dict.get('authors', [])) > len(existing_dict.get('authors', [])):
            merged['authors'] = new_dict['authors']

        # Abstract: Keep longer one (usually more complete)
        existing_abstract = existing_dict.get('abstract') or ''
        new_abstract = new_dict.get('abstract') or ''
        if len(new_abstract) > len(existing_abstract):
            merged['abstract'] = new_dict['abstract']

        # DOI: Prefer non-null
        if not merged.get('doi') and new_dict.get('doi'):
            merged['doi'] = new_dict['doi']

        # ArXiv ID: Prefer non-null
        if not merged.get('arxiv_id') and new_dict.get('arxiv_id'):
            merged['arxiv_id'] = new_dict['arxiv_id']

        # URLs: Keep both if different (prefer PDF URLs)
        if new_dict.get('url') and not merged.get('url'):
            merged['url'] = new_dict['url']

        if new_dict.get('pdf_url') and not merged.get('pdf_url'):
            merged['pdf_url'] = new_dict['pdf_url']

        # Keywords: Merge and deduplicate
        existing_keywords = set(existing_dict.get('keywords', []))
        new_keywords = set(new_dict.get('keywords', []))
        merged['keywords'] = list(existing_keywords | new_keywords)

        # Publication date: Keep if missing
        if not merged.get('publication_date') and new_dict.get('publication_date'):
            merged['publication_date'] = new_dict['publication_date']

        # Journal: Prefer more specific/longer name
        if len(new_dict.get('journal', '') or '') > len(
            merged.get('journal', '') or ''
        ):
            merged['journal'] = new_dict['journal']

        # Additional metadata: Merge dictionaries
        existing_meta = existing_dict.get('additional_metadata', {}) or {}
        new_meta = new_dict.get('additional_metadata', {}) or {}
        merged['additional_metadata'] = {**existing_meta, **new_meta}

        # Track which sources contributed
        sources = merged['additional_metadata'].get('merged_from_sources', [])
        if existing_dict.get('source') not in sources:
            sources.append(existing_dict.get('source'))
        if new_dict.get('source') not in sources:
            sources.append(new_dict.get('source'))
        merged['additional_metadata']['merged_from_sources'] = sources

        # Update timestamp to latest
        merged['scrape_timestamp'] = new_dict.get(
            'scrape_timestamp'
        ) or existing_dict.get('scrape_timestamp')

        # Create merged article
        return ScrapedArticleMetadata(**merged)

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
            elif source.source_type == 'browser_workflow' and source.api_config:
                # Browser workflows require async execution via the orchestrator.
                # If we got here through a sync path, log and skip gracefully.
                logger.warning(
                    f'Browser workflow source {source.name} requires async execution. '
                    'Use DiscoveryOrchestrator for browser workflow discovery.'
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
                # TODO: self.filter is not initialized in __init__. This is a dead
                # reference — the newer DiscoveryService._filter_articles() in
                # services/discovery_service.py replaced this pattern using
                # article_service.evaluate_for_download(). This legacy code path
                # will raise AttributeError at runtime until self.filter is wired
                # up or this method is rewritten to use ArticleService.
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
