"""
ArXiv API source for article discovery.

This module provides the ArXiv API client and source implementation
for discovering academic papers from the arXiv preprint server.
"""

import time
import urllib.parse
import warnings
from datetime import datetime
from typing import Any

import httpx
import requests
from bs4 import BeautifulSoup
from loguru import logger

from thoth.utilities.schemas import ArxivPaper, Citation, ScrapedArticleMetadata

from .base import BaseAPISource


class ArxivClient:
    """Client for interacting with arXiv API to retrieve citation metadata."""

    def __init__(
        self,
        base_url: str = 'https://export.arxiv.org/api/query',
        timeout: int = 10,
        delay_seconds: float = 3.0,
        max_retries: int = 9,
    ):
        """
        Initialize arXiv API client.

        Args:
            base_url: Base URL for the arXiv API.
            timeout: Timeout for API requests in seconds.
            delay_seconds: Delay between API requests to avoid rate limiting.
            max_retries: Maximum number of retry attempts for failed requests.
        """
        self.base_url = base_url
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries

        headers = {
            'User-Agent': 'Thoth/1.0 (https://github.com/nick-ghafari/project-thoth)'
        }
        self.client = httpx.Client(timeout=timeout, headers=headers)
        self.last_request_time = 0

    def _make_request(
        self,
        params: dict[str, Any],
    ) -> str:
        """
        Make a request to the arXiv API with rate limiting.

        Args:
            params: API query parameters.

        Returns:
            str: Raw XML response from the arXiv API.

        Raises:
            httpx.HTTPError: If the request fails after retries.
        """
        # Implement rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.delay_seconds:
            sleep_time = self.delay_seconds - time_since_last_request
            logger.debug(f'Rate limiting: sleeping for {sleep_time:.2f} seconds')
            time.sleep(sleep_time)

        url = f'{self.base_url}?{urllib.parse.urlencode(params)}'

        retries = 0
        while retries <= self.max_retries:
            try:
                logger.debug(f'Making request to arXiv API: {url}')
                response = self.client.get(url)
                response.raise_for_status()
                self.last_request_time = time.time()

                return response.text
            except httpx.HTTPError as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(
                        f'Failed to make arXiv API request after {self.max_retries} retries: {e}'
                    )
                    raise
                logger.warning(
                    f'arXiv API request failed (attempt {retries}/{self.max_retries}): {e}'
                )
                time.sleep(self.delay_seconds * retries)  # Exponential backoff

    def search(
        self,
        query: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = 'relevance',
        sort_order: str = 'descending',
        search_field: str | None = None,
    ) -> list[ArxivPaper]:
        """
        Search arXiv for papers matching the query.

        Args:
            query: Search query.
            start: Starting index for results.
            max_results: Maximum number of results to return.
            sort_by: Sort criteria ("relevance", "lastUpdatedDate", "submittedDate").
            sort_order: Sort order ("ascending" or "descending").
            search_field: Field to search in ("all", "title", "abstract", "author", etc.)

        Returns:
            List[ArxivPaper]: List of arXiv papers matching the search criteria.
        """
        if search_field:
            search_query = f'{search_field}:{query}'
        else:
            search_query = query

        params = {
            'search_query': search_query,
            'start': start,
            'max_results': max_results,
            'sortBy': sort_by,
            'sortOrder': sort_order,
        }

        xml_response = self._make_request(params)

        # Parse the XML response
        return self._parse_arxiv_response(xml_response)

    def get_by_id(self, paper_id: str | list[str]) -> list[ArxivPaper]:
        """
        Get arXiv papers by their IDs.

        Args:
            paper_id: Single arXiv ID or list of IDs.

        Returns:
            List[ArxivPaper]: List of papers with the specified IDs.
        """
        if isinstance(paper_id, str):
            id_list = paper_id
        else:
            id_list = ','.join(paper_id)

        params = {
            'id_list': id_list,
            'max_results': len(paper_id) if isinstance(paper_id, list) else 1,
        }

        xml_response = self._make_request(params)

        # Parse the XML response
        return self._parse_arxiv_response(xml_response)

    def _parse_arxiv_response(self, xml_response: str) -> list[ArxivPaper]:
        """
        Parse arXiv API response XML into ArxivPaper objects.

        Args:
            xml_response: XML response from arXiv API.

        Returns:
            List[ArxivPaper]: List of parsed ArxivPaper objects.
        """
        results = []

        # Use BeautifulSoup to parse XML
        soup = BeautifulSoup(xml_response, 'xml')

        # Find all entry elements (each represents a paper)
        entries = soup.find_all('entry')

        for entry in entries:
            try:
                # Extract basic metadata
                entry_id = entry.find('id').text if entry.find('id') else ''
                arxiv_id = (
                    entry_id.split('/abs/')[-1] if '/abs/' in entry_id else entry_id
                )

                title = entry.find('title').text.strip() if entry.find('title') else ''
                abstract = (
                    entry.find('summary').text.strip() if entry.find('summary') else ''
                )

                # Extract authors
                authors = []
                author_elements = entry.find_all('author')
                for author_elem in author_elements:
                    name_elem = author_elem.find('name')
                    if name_elem:
                        authors.append(name_elem.text.strip())

                # Extract PDF link
                pdf_url = None
                for link in entry.find_all('link'):
                    if (
                        link.get('title') == 'pdf'
                        or link.get('type') == 'application/pdf'
                    ):
                        pdf_url = link.get('href')
                        break

                # Extract DOI if available
                doi = None
                arxiv_doi = entry.find('arxiv:doi')
                if arxiv_doi:
                    doi = arxiv_doi.text.strip()

                # Extract published/updated dates
                published = (
                    entry.find('published').text if entry.find('published') else None
                )
                updated = entry.find('updated').text if entry.find('updated') else None

                # Extract comment if available
                comment = None
                arxiv_comment = entry.find('arxiv:comment')
                if arxiv_comment:
                    comment = arxiv_comment.text.strip()

                # Extract journal reference if available
                journal_ref = None
                arxiv_journal_ref = entry.find('arxiv:journal_ref')
                if arxiv_journal_ref:
                    journal_ref = arxiv_journal_ref.text.strip()

                # Extract categories
                categories = []
                for category in entry.find_all('category'):
                    term = category.get('term')
                    if term:
                        categories.append(term)

                paper = ArxivPaper(
                    id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    categories=categories,
                    pdf_url=pdf_url,
                    published=published,
                    updated=updated,
                    comment=comment,
                    journal_ref=journal_ref,
                    doi=doi,
                )
                results.append(paper)
            except Exception as e:
                logger.error(f'Error parsing arXiv entry: {e}')

        return results

    def arxiv_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Lookup citations in arXiv and enhance with additional metadata.

        Args:
            citations: List of citations to enhance.

        Returns:
            List[Citation]: The citations with enhanced information from arXiv.
        """
        logger.debug(f'Looking up {len(citations)} citations in arXiv')

        for citation in citations:
            # Skip if there's no title or if there's already a DOI
            if not citation.title:
                continue

            # Search for the paper by title
            query = f'"{citation.title}"'
            try:
                search_results = self.search(query, max_results=1, search_field='ti')

                if not search_results:
                    logger.debug(f'No arXiv results found for title: {citation.title}')
                    continue

                paper = search_results[0]

                # Update citation with arXiv data
                self._update_citation_from_arxiv(citation, paper)

                # If we found an arXiv ID but no DOI, set it as a backup_id
                if not citation.doi and not citation.backup_id:
                    citation.backup_id = f'arxiv:{paper.id}'

                # Get citation count if needed
                if citation.citation_count is None:
                    citation.citation_count = self.get_citation_count(paper.id)

            except Exception as e:
                logger.error(f'Error enhancing citation with arXiv: {e}')

        return citations

    def _update_citation_from_arxiv(
        self, citation: Citation, paper: ArxivPaper
    ) -> None:
        """
        Update citation with information from ArxivPaper.

        Args:
            citation: The citation to update.
            paper: ArxivPaper with source information.
        """
        # Update citation with arXiv paper data if fields are missing
        if not citation.doi and paper.doi:
            citation.doi = paper.doi

        if not citation.url and paper.pdf_url:
            citation.url = paper.pdf_url

        if not citation.journal and paper.journal_ref:
            citation.journal = paper.journal_ref

        if not citation.authors and paper.authors:
            citation.authors = paper.authors

        # If we have a year in the paper metadata or can extract from published date
        if not citation.year and paper.published:
            try:
                # Parse the date string and extract the year
                date = datetime.fromisoformat(paper.published.replace('Z', '+00:00'))
                citation.year = date.year
            except Exception:
                # If parsing fails, don't update the year
                pass

        if not citation.abstract and paper.abstract:
            citation.abstract = paper.abstract
        if not citation.venue and hasattr(paper, 'venue') and paper.venue:
            citation.venue = paper.venue
        if (
            citation.citation_count is None
            and hasattr(paper, 'citation_count')
            and paper.citation_count is not None
        ):
            citation.citation_count = paper.citation_count

    def get_citation_count(self, paper_id: str) -> int | None:
        """
        Get the citation count for an arXiv paper by querying Semantic Scholar.

        Args:
            paper_id: The arXiv ID of the paper.

        Returns:
            Optional[int]: The citation count if found, None otherwise.
        """
        try:
            # Use Semantic Scholar to get citation counts for arXiv papers
            semantic_url = f'https://api.semanticscholar.org/v1/paper/arXiv:{paper_id}'
            response = self.client.get(semantic_url)
            response.raise_for_status()
            data = response.json()

            citation_count = data.get('citationCount')
            return citation_count
        except Exception as e:
            logger.error(f'Failed to get citation count for arXiv:{paper_id}: {e}')
            return None

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


class ArxivAPISource(BaseAPISource):
    """Deprecated ArXiv API source.

    This class remains for backwards compatibility and will be removed in a
    future release. Use :class:`thoth.discovery.plugins.arxiv_plugin.ArxivPlugin`
    instead.
    """

    def __init__(self, rate_limit_delay: float = 3.0):
        """
        Initialize the ArXiv API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds.
        """
        warnings.warn(
            'ArxivAPISource is deprecated and will be removed in a future release. '
            'Use ArxivPlugin instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        self.base_url = 'https://export.arxiv.org/api/query'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search ArXiv for papers.

        Args:
            config: Configuration dictionary containing search parameters.
                   Expected keys:
                   - categories: List of ArXiv categories (e.g., ['cs.LG', 'cs.AI'])
                   - keywords: List of keywords to search for
                   - start_date: Start date for search (YYYY-MM-DD)
                   - end_date: End date for search (YYYY-MM-DD)
                   - sort_by: Sort order ('relevance', 'lastUpdatedDate', 'submittedDate')
                   - sort_order: Sort direction ('ascending', 'descending')
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.

        Example:
            >>> source = ArxivAPISource()
            >>> config = {
            ...     'categories': ['cs.LG', 'cs.AI'],
            ...     'keywords': ['machine learning', 'neural networks'],
            ...     'max_results': 10,
            ... }
            >>> articles = source.search(config, max_results=10)
        """
        try:
            # Build search query
            query_parts = []

            # Add category filters
            categories = config.get('categories', [])
            if categories:
                cat_queries = [f'cat:{cat}' for cat in categories]
                query_parts.append(f'({" OR ".join(cat_queries)})')

            # Add keyword searches
            keywords = config.get('keywords', [])
            if keywords:
                # Search in title, abstract, and comments
                keyword_queries = []
                for keyword in keywords:
                    keyword_queries.append(f'(ti:"{keyword}" OR abs:"{keyword}")')
                query_parts.append(f'({" OR ".join(keyword_queries)})')

            # Combine query parts
            if not query_parts:
                # Default to recent papers in computer science if no specific criteria
                query = 'cat:cs.*'
            else:
                query = ' AND '.join(query_parts)

            # Build parameters
            params = {
                'search_query': query,
                'start': 0,
                'max_results': min(max_results, 1000),  # ArXiv API limit
                'sortBy': config.get('sort_by', 'lastUpdatedDate'),
                'sortOrder': config.get('sort_order', 'descending'),
            }

            logger.info(f'Searching ArXiv with query: {query}')

            # Rate limiting
            self._rate_limit()

            # Make API request
            headers = {
                'User-Agent': 'Thoth/1.0 (https://github.com/nick-ghafari/project-thoth)'
            }
            response = requests.get(
                self.base_url, params=params, timeout=30, headers=headers
            )
            response.raise_for_status()

            # Parse XML response
            soup = BeautifulSoup(response.content, 'xml')
            entries = soup.find_all('entry')

            articles = []
            for entry in entries:
                try:
                    # Extract paper metadata
                    article = self._parse_arxiv_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f'Error parsing ArXiv entry: {e}')
                    continue

            logger.info(f'Found {len(articles)} articles from ArXiv')
            return articles

        except Exception as e:
            logger.error(f'ArXiv API search failed: {e}')
            return []

    def _rate_limit(self) -> None:
        """Apply rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f'Rate limiting: sleeping {sleep_time:.2f}s')
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _parse_arxiv_entry(self, entry) -> ScrapedArticleMetadata | None:
        """Parse a single ArXiv entry into ScrapedArticleMetadata."""
        try:
            # Extract basic fields
            title = entry.find('title').text.strip() if entry.find('title') else ''
            abstract = (
                entry.find('summary').text.strip() if entry.find('summary') else ''
            )

            if not title:
                return None

            # Extract authors
            authors = []
            for author in entry.find_all('author'):
                name = author.find('name')
                if name:
                    authors.append(name.text.strip())

            # Extract ArXiv ID and create URL
            entry_id = entry.find('id').text if entry.find('id') else ''
            arxiv_id = entry_id.split('/abs/')[-1] if '/abs/' in entry_id else ''
            url = f'https://arxiv.org/abs/{arxiv_id}' if arxiv_id else entry_id

            # Extract publication date
            published = entry.find('published')
            pub_date = None
            if published:
                try:
                    pub_date = datetime.fromisoformat(
                        published.text.replace('Z', '+00:00')
                    )
                except Exception:
                    pass

            # Extract categories/tags
            categories = []
            for category in entry.find_all('category'):
                term = category.get('term')
                if term:
                    categories.append(term)

            # Create metadata object
            article = ScrapedArticleMetadata(
                title=title,
                url=url,
                authors=authors,
                published_date=pub_date.isoformat() if pub_date else None,
                abstract=abstract,
                source='arxiv',
                tags=categories,
                metadata={
                    'arxiv_id': arxiv_id,
                    'entry_id': entry_id,
                },
            )

            return article

        except Exception as e:
            logger.error(f'Error parsing ArXiv entry: {e}')
            return None

    def get_required_config_keys(self) -> list[str]:
        """Get required configuration keys."""
        return []  # No required keys for ArXiv

    def get_optional_config_keys(self) -> list[str]:
        """Get optional configuration keys."""
        return [
            'categories',
            'keywords',
            'start_date',
            'end_date',
            'sort_by',
            'sort_order',
        ]
