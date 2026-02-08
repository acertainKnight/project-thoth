"""Papers with Code discovery plugin for finding papers with implementations.

This plugin uses the free Papers with Code REST API to discover papers
that have associated code repositories and benchmark results.
"""

from __future__ import annotations

import time
from datetime import datetime

import httpx

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from .base import BaseDiscoveryPlugin


class PapersWithCodePlugin(BaseDiscoveryPlugin):
    """Discovery plugin for Papers with Code API.

    Uses the free REST API at paperswithcode.com/api/v1/.
    No API key required.
    """

    BASE_URL = 'https://paperswithcode.com/api/v1'

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the Papers with Code plugin.

        Args:
            config: Configuration dictionary with optional keys:
                - arxiv_only: Only return papers with arXiv IDs (default: False)
                - has_code: Only return papers with code (default: True)
                - min_stars: Minimum GitHub stars for code repo
                - rate_limit_delay: Delay between requests in seconds (default: 1.0)
        """
        super().__init__(config)
        self.rate_limit_delay = self.config.get('rate_limit_delay', 1.0)
        self.last_request_time = 0.0

        # Initialize HTTP client
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                'User-Agent': 'Thoth/1.0 (https://github.com/nick-ghafari/project-thoth)',
            },
        )

    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover papers from Papers with Code.

        Args:
            query: Research query with keywords and topics.
            max_results: Maximum number of papers to return.

        Returns:
            List of discovered papers as ScrapedArticleMetadata.
        """
        has_code = self.config.get('has_code', True)
        arxiv_only = self.config.get('arxiv_only', False)
        min_stars = self.config.get('min_stars')

        # Build search query from keywords
        keywords = query.keywords or []
        search_query = ' '.join(keywords) if keywords else query.research_question

        self.logger.info(
            f"Searching Papers with Code: query='{search_query}', "
            f'has_code={has_code}, max_results={max_results}'
        )

        results: list[ScrapedArticleMetadata] = []
        page = 1
        items_per_page = min(50, max_results)

        try:
            while len(results) < max_results:
                # Build request parameters
                params = {
                    'page': page,
                    'items_per_page': items_per_page,
                }

                # Add search query if provided
                if search_query and search_query.strip():
                    params['q'] = search_query

                # Make API request with rate limiting
                self._rate_limit()
                response = self.client.get(
                    f'{self.BASE_URL}/papers/',
                    params=params,
                )
                response.raise_for_status()

                data = response.json()
                papers = data.get('results', [])

                if not papers:
                    break  # No more results

                # Convert papers to metadata
                for paper in papers:
                    # Apply filters
                    if has_code:
                        repo_count = len(paper.get('repositories', []))
                        if repo_count == 0:
                            continue

                    if arxiv_only and not paper.get('arxiv_id'):
                        continue

                    if min_stars and not self._meets_star_threshold(paper, min_stars):
                        continue

                    # Convert to metadata
                    metadata = self._paper_to_metadata(paper)
                    if metadata:
                        results.append(metadata)

                    if len(results) >= max_results:
                        break

                # Check if there's a next page
                if not data.get('next'):
                    break

                page += 1

            self.logger.info(f'Found {len(results)} papers from Papers with Code')
            return results[:max_results]

        except Exception as e:
            self.logger.error(f'Papers with Code search failed: {e}')
            return []

    def _rate_limit(self) -> None:
        """Apply rate limiting between API requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _meets_star_threshold(self, paper: dict, min_stars: int) -> bool:
        """Check if paper's code repo meets minimum star threshold.

        Args:
            paper: Paper data from Papers with Code API.
            min_stars: Minimum number of GitHub stars.

        Returns:
            True if any repo meets threshold, False otherwise.
        """
        repositories = paper.get('repositories', [])
        for repo in repositories:
            stars = repo.get('stars', 0)
            if stars >= min_stars:
                return True
        return False

    def _paper_to_metadata(self, paper: dict) -> ScrapedArticleMetadata | None:
        """Convert Papers with Code paper to ScrapedArticleMetadata.

        Args:
            paper: Paper data from Papers with Code API.

        Returns:
            ScrapedArticleMetadata or None if conversion fails.
        """
        try:
            title = paper.get('title')
            if not title:
                return None

            # Extract authors (list of author names)
            authors = paper.get('authors', [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(',')]

            # Extract abstract
            abstract = paper.get('abstract')

            # Extract publication info
            published = paper.get('published')

            # Extract ArXiv ID and DOI
            arxiv_id = paper.get('arxiv_id')

            # Build paper URL
            paper_id = paper.get('id')
            paper_url = paper.get('url_abs') or paper.get('url_pdf')
            pwc_url = (
                f'https://paperswithcode.com/paper/{paper_id}' if paper_id else None
            )

            # Extract PDF URL
            pdf_url = paper.get('url_pdf')

            # Extract code repositories
            repositories = paper.get('repositories', [])
            repo_urls = [repo.get('url') for repo in repositories if repo.get('url')]

            # Extract tasks and methods
            tasks = [t.get('task') for t in paper.get('tasks', []) if t.get('task')]
            methods = [m.get('name') for m in paper.get('methods', []) if m.get('name')]

            # Build keywords from tasks and methods
            keywords = []
            if tasks:
                keywords.extend(tasks[:5])
            if methods:
                keywords.extend(methods[:5])

            # Build additional metadata
            additional_metadata = {
                'paperswithcode_id': paper_id,
                'paperswithcode_url': pwc_url,
                'conference': paper.get('conference'),
                'proceedings': paper.get('proceedings'),
            }

            if repositories:
                additional_metadata['repositories'] = [
                    {
                        'url': r.get('url'),
                        'stars': r.get('stars'),
                        'framework': r.get('framework'),
                    }
                    for r in repositories
                ]
                additional_metadata['num_repositories'] = len(repositories)

            if tasks:
                additional_metadata['tasks'] = tasks
            if methods:
                additional_metadata['methods'] = methods

            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=published,
                journal=paper.get('conference') or paper.get('proceedings'),
                arxiv_id=arxiv_id,
                url=paper_url or pwc_url,
                pdf_url=pdf_url,
                keywords=keywords,
                source='paperswithcode',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata=additional_metadata,
            )

        except Exception as e:
            self.logger.error(f'Error converting Papers with Code paper: {e}')
            return None

    def validate_config(self, config: dict) -> bool:
        """Validate the configuration.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            True if valid, False otherwise.
        """
        # No required fields
        return True

    def get_name(self) -> str:
        """Return the plugin name."""
        return 'paperswithcode'
