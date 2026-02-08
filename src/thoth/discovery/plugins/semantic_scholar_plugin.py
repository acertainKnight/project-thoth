"""Semantic Scholar discovery plugin for venue-filtered paper search.

This plugin uses the free Semantic Scholar REST API to search for papers
with venue filtering, citation counts, and comprehensive metadata.
"""

from __future__ import annotations

import time
from datetime import datetime

import httpx

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from .base import BaseDiscoveryPlugin


class SemanticScholarPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for Semantic Scholar API.

    Uses the free (rate-limited) REST API at api.semanticscholar.org.
    No API key required, but rate-limited to ~1 request/second.
    """

    BASE_URL = 'https://api.semanticscholar.org/graph/v1'

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the Semantic Scholar plugin.

        Args:
            config: Configuration dictionary with optional keys:
                - venue: Venue name filter (e.g., 'NeurIPS', 'ICML', 'AAAI')
                - year: Year filter (e.g., 2024)
                - fields_of_study: List of fields (e.g., ['Computer Science'])
                - rate_limit_delay: Delay between requests in seconds (default: 1.1)
                - min_citation_count: Minimum citation count filter
        """
        super().__init__(config)
        self.rate_limit_delay = self.config.get('rate_limit_delay', 1.1)
        self.last_request_time = 0.0

        # Initialize HTTP client with headers
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                'User-Agent': 'Thoth/1.0 (https://github.com/nick-ghafari/project-thoth)',
            },
        )

    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover papers from Semantic Scholar.

        Args:
            query: Research query with keywords and topics.
            max_results: Maximum number of papers to return.

        Returns:
            List of discovered papers as ScrapedArticleMetadata.
        """
        venue = self.config.get('venue')
        year = self.config.get('year')
        fields_of_study = self.config.get('fields_of_study', ['Computer Science'])
        min_citation_count = self.config.get('min_citation_count')

        # Build search query from keywords
        keywords = query.keywords or []
        search_query = ' '.join(keywords) if keywords else query.research_question

        self.logger.info(
            f"Searching Semantic Scholar: query='{search_query}', "
            f'venue={venue}, year={year}, max_results={max_results}'
        )

        results: list[ScrapedArticleMetadata] = []
        offset = 0
        limit = min(100, max_results)  # API limit per request

        try:
            while len(results) < max_results:
                # Build request parameters
                params = {
                    'query': search_query,
                    'offset': offset,
                    'limit': limit,
                    'fields': 'paperId,title,authors,abstract,year,venue,citationCount,url,externalIds,fieldsOfStudy,publicationDate',
                }

                # Add filters
                if venue:
                    params['venue'] = venue
                if year:
                    params['year'] = str(year)
                if fields_of_study:
                    params['fieldsOfStudy'] = ','.join(fields_of_study)
                if min_citation_count:
                    params['minCitationCount'] = str(min_citation_count)

                # Make API request with rate limiting
                self._rate_limit()
                response = self.client.get(
                    f'{self.BASE_URL}/paper/search',
                    params=params,
                )
                response.raise_for_status()

                data = response.json()
                papers = data.get('data', [])

                if not papers:
                    break  # No more results

                # Convert papers to metadata
                for paper in papers:
                    metadata = self._paper_to_metadata(paper)
                    if metadata:
                        results.append(metadata)

                    if len(results) >= max_results:
                        break

                # Check if there are more results
                total = data.get('total', 0)
                if offset + limit >= total:
                    break

                offset += limit

            self.logger.info(f'Found {len(results)} papers from Semantic Scholar')
            return results[:max_results]

        except Exception as e:
            self.logger.error(f'Semantic Scholar search failed: {e}')
            return []

    def _rate_limit(self) -> None:
        """Apply rate limiting between API requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _paper_to_metadata(self, paper: dict) -> ScrapedArticleMetadata | None:
        """Convert Semantic Scholar paper to ScrapedArticleMetadata.

        Args:
            paper: Paper data from Semantic Scholar API.

        Returns:
            ScrapedArticleMetadata or None if conversion fails.
        """
        try:
            title = paper.get('title')
            if not title:
                return None

            # Extract authors
            authors = []
            for author in paper.get('authors', []):
                name = author.get('name')
                if name:
                    authors.append(name)

            # Extract abstract
            abstract = paper.get('abstract')

            # Extract year and publication date
            year = paper.get('year')
            pub_date = paper.get('publicationDate') or (str(year) if year else None)

            # Extract venue
            venue = paper.get('venue')

            # Extract citation count
            citation_count = paper.get('citationCount')

            # Extract external IDs (DOI, ArXiv ID, etc.)
            external_ids = paper.get('externalIds', {})
            doi = external_ids.get('DOI')
            arxiv_id = external_ids.get('ArXiv')

            # Extract fields of study
            fields_of_study = paper.get('fieldsOfStudy', [])

            # Build URL
            paper_id = paper.get('paperId')
            paper_url = paper.get('url') or (
                f'https://www.semanticscholar.org/paper/{paper_id}'
                if paper_id
                else None
            )

            # Build additional metadata
            additional_metadata = {
                'semantic_scholar_id': paper_id,
                'citation_count': citation_count,
                'fields_of_study': fields_of_study,
            }

            if external_ids:
                additional_metadata['external_ids'] = external_ids

            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=pub_date,
                journal=venue,
                doi=doi,
                arxiv_id=arxiv_id,
                url=paper_url,
                keywords=fields_of_study[:5]
                if fields_of_study
                else [],  # Use top fields
                source='semantic_scholar',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata=additional_metadata,
            )

        except Exception as e:
            self.logger.error(f'Error converting Semantic Scholar paper: {e}')
            return None

    def validate_config(self, config: dict) -> bool:
        """Validate the configuration.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            True if valid, False otherwise.
        """
        # No required fields for Semantic Scholar
        return True

    def get_name(self) -> str:
        """Return the plugin name."""
        return 'semantic_scholar'
