"""
Crossref API resolver for citation enrichment.

This module provides async methods to resolve citations using the Crossref API,
following best practices for query construction, rate limiting, and error handling.
"""

import asyncio
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from thoth.utilities.schemas import Citation


@dataclass
class MatchCandidate:
    """Represents a potential match from Crossref API."""

    doi: str
    title: str
    authors: list[str] | None = None
    container_title: str | None = None  # Journal/venue name
    year: int | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    url: str | None = None
    score: float | None = None  # Crossref relevance score
    abstract: str | None = None
    publisher: str | None = None
    is_open_access: bool | None = None
    citation_count: int | None = None

    def to_citation(self) -> Citation:
        """Convert MatchCandidate to Citation object."""
        return Citation(
            doi=self.doi,
            title=self.title,
            authors=self.authors,
            journal=self.container_title,
            venue=self.container_title,
            year=self.year,
            volume=self.volume,
            issue=self.issue,
            pages=self.pages,
            url=self.url,
            abstract=self.abstract,
            is_open_access=self.is_open_access,
            citation_count=self.citation_count,
        )


class CrossrefResolver:
    """
    Async resolver for Crossref API with rate limiting and caching.

    Features:
    - Async HTTP requests using httpx
    - Configurable rate limiting (default: 50 req/s)
    - Persistent SQLite caching
    - Exponential backoff with retries
    - Query construction following Crossref best practices
    - Response parsing according to Crossref schema
    """

    BASE_URL = 'https://api.crossref.org/works'

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit: int = 50,  # requests per second
        max_retries: int = 3,
        timeout: int = 30,
        cache_dir: str | None = None,
        enable_caching: bool = True,
    ):
        """
        Initialize Crossref resolver.

        Args:
            api_key: Optional Crossref Plus API key for higher rate limits
            rate_limit: Maximum requests per second (default: 50)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            cache_dir: Directory for persistent cache
            enable_caching: Whether to enable response caching
        """
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_caching = enable_caching

        # Rate limiting
        self._rate_limiter = asyncio.Semaphore(rate_limit)
        self._last_request_time = 0.0
        self._min_request_interval = 1.0 / rate_limit

        # HTTP client
        self._client: httpx.AsyncClient | None = None

        # Cache setup
        self.cache_dir = Path(cache_dir) if cache_dir else Path('./cache/crossref')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'api_cache.db'
        if enable_caching:
            self._init_cache()

        # Statistics
        self._stats = {
            'api_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'retries': 0,
        }

        logger.info(
            f'Initialized CrossrefResolver with rate_limit={rate_limit} req/s, '
            f'caching={"enabled" if enable_caching else "disabled"}'
        )

    def _init_cache(self) -> None:
        """Initialize SQLite cache database with WAL mode for concurrent writes."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # ALWAYS enable WAL mode for concurrent read/write access
            # This is persistent and will convert existing databases to WAL
            current_mode = cursor.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            cursor.execute("PRAGMA synchronous=NORMAL")  # Better performance with WAL

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crossref_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_data TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON crossref_cache(timestamp)
            """)
            conn.commit()
            conn.close()
            logger.info(f'Crossref cache at {self.db_path} using {current_mode} mode')
        except Exception as e:
            logger.error(f'Failed to initialize Crossref cache: {e}')

    def _generate_cache_key(self, query_params: dict[str, Any]) -> str:
        """Generate unique cache key from query parameters."""
        key_string = json.dumps(query_params, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve cached response."""
        if not self.enable_caching:
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                'SELECT response_data FROM crossref_cache WHERE cache_key = ?',
                (cache_key,),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                self._stats['cache_hits'] += 1
                logger.debug(f'Cache HIT for key {cache_key[:16]}...')
                return json.loads(row[0])

            self._stats['cache_misses'] += 1
            return None
        except Exception as e:
            logger.error(f'Error reading from cache: {e}')
            return None

    def _save_to_cache(self, cache_key: str, data: dict[str, Any]) -> None:
        """Save response to cache."""
        if not self.enable_caching or not data:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO crossref_cache
                (cache_key, response_data, timestamp)
                VALUES (?, ?, ?)
                """,
                (cache_key, json.dumps(data), time.time()),
            )
            conn.commit()
            conn.close()
            logger.debug(f'Saved to cache: {cache_key[:16]}...')
        except Exception as e:
            logger.error(f'Error writing to cache: {e}')

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            headers = {
                'User-Agent': 'ThothResearchAssistant/1.0 (mailto:research@example.com)',
            }
            if self.api_key:
                headers['Crossref-Plus-API-Token'] = f'Bearer {self.api_key}'

            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rate_limited_request(
        self, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Make rate-limited request to Crossref API.

        Args:
            params: Query parameters

        Returns:
            API response data or None on failure
        """
        # Check cache first
        cache_key = self._generate_cache_key(params)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        async with self._rate_limiter:
            # Enforce minimum interval between requests
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            if time_since_last < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - time_since_last)

            for attempt in range(self.max_retries + 1):
                try:
                    logger.debug(
                        f'Crossref API request (attempt {attempt + 1}): {params}'
                    )

                    response = await self.client.get(self.BASE_URL, params=params)
                    self._last_request_time = time.time()

                    response.raise_for_status()
                    self._stats['api_calls'] += 1

                    data = response.json()
                    self._save_to_cache(cache_key, data)
                    return data

                except httpx.HTTPStatusError as e:
                    self._stats['errors'] += 1
                    logger.warning(
                        f'Crossref API error (attempt {attempt + 1}): '
                        f'Status {e.response.status_code}'
                    )

                    # Handle rate limiting
                    if e.response.status_code == 429:
                        if attempt < self.max_retries:
                            retry_after = e.response.headers.get('Retry-After', '60')
                            try:
                                wait_time = min(int(retry_after), 300)  # Max 5 min
                            except ValueError:
                                wait_time = 60

                            logger.info(
                                f'Rate limited. Waiting {wait_time}s before retry.'
                            )
                            await asyncio.sleep(wait_time)
                            self._stats['retries'] += 1
                            continue

                    # Exponential backoff for server errors
                    if e.response.status_code >= 500 and attempt < self.max_retries:
                        wait_time = min(2**attempt, 60)
                        logger.info(f'Server error. Retrying in {wait_time}s.')
                        await asyncio.sleep(wait_time)
                        self._stats['retries'] += 1
                        continue

                    # Don't retry other errors
                    logger.error(f'Crossref API request failed: {e}')
                    return None

                except httpx.RequestError as e:
                    self._stats['errors'] += 1
                    logger.warning(
                        f'Crossref request error (attempt {attempt + 1}): {e}'
                    )

                    if attempt < self.max_retries:
                        wait_time = min(2**attempt, 30)
                        await asyncio.sleep(wait_time)
                        self._stats['retries'] += 1
                        continue

                    logger.error(f'Crossref request failed after retries: {e}')
                    return None

                except Exception as e:
                    self._stats['errors'] += 1
                    logger.error(f'Unexpected error in Crossref request: {e}')
                    return None

        return None

    def _build_query(self, citation: Citation) -> dict[str, Any]:
        """
        Build Crossref API query following best practices.

        Query construction:
        - query.title: Title of the work
        - query.author: Author name
        - query.container-title: Journal/venue name
        - filter: Year range filtering

        Args:
            citation: Citation to resolve

        Returns:
            Query parameters dict
        """
        params = {'rows': 5}  # Return top 5 matches

        query_parts = []

        # Add title to query
        if citation.title:
            query_parts.append(f'query.title="{citation.title}"')

        # Add author to query (first author if multiple)
        if citation.authors and len(citation.authors) > 0:
            first_author = citation.authors[0]
            query_parts.append(f'query.author="{first_author}"')

        # Add container title (journal/venue)
        if citation.journal:
            query_parts.append(f'query.container-title="{citation.journal}"')
        elif citation.venue:
            query_parts.append(f'query.container-title="{citation.venue}"')

        # Combine query parts
        if query_parts:
            params['query'] = ' '.join(query_parts)

        # Add year filter if available
        if citation.year:
            # Filter by year with ±1 year tolerance
            params['filter'] = (
                f'from-pub-date:{citation.year - 1},until-pub-date:{citation.year + 1}'
            )

        return params

    def _parse_work(self, work: dict[str, Any]) -> MatchCandidate:
        """
        Parse Crossref work item into MatchCandidate.

        Args:
            work: Work item from Crossref API response

        Returns:
            MatchCandidate with parsed metadata
        """
        # Extract authors
        authors = None
        if 'author' in work:
            authors = []
            for author in work['author']:
                if 'given' in author and 'family' in author:
                    authors.append(f'{author["given"]} {author["family"]}')
                elif 'family' in author:
                    authors.append(author['family'])

        # Extract year
        year = None
        if 'published-print' in work:
            date_parts = work['published-print'].get('date-parts', [[]])
            if date_parts and len(date_parts[0]) > 0:
                year = date_parts[0][0]
        elif 'published-online' in work:
            date_parts = work['published-online'].get('date-parts', [[]])
            if date_parts and len(date_parts[0]) > 0:
                year = date_parts[0][0]

        # Extract container title (journal)
        container_title = None
        if 'container-title' in work and work['container-title']:  # noqa: RUF019
            container_title = work['container-title'][0]

        # Extract pages
        pages = work.get('page')

        # Extract URL
        url = work.get('URL')

        # Extract open access status
        is_open_access = None
        if 'is-referenced-by-count' in work:
            # Crossref provides this in link section
            for link in work.get('link', []):
                if link.get('content-type') == 'application/pdf':
                    is_open_access = True
                    break

        return MatchCandidate(
            doi=work['DOI'],
            title=work.get('title', [''])[0] if 'title' in work else '',
            authors=authors,
            container_title=container_title,
            year=year,
            volume=work.get('volume'),
            issue=work.get('issue'),
            pages=pages,
            url=url,
            score=work.get('score'),
            abstract=work.get('abstract'),
            publisher=work.get('publisher'),
            is_open_access=is_open_access,
            citation_count=work.get('is-referenced-by-count'),
        )

    async def resolve_citation(self, citation: Citation) -> list[MatchCandidate]:
        """
        Resolve a single citation using Crossref API.

        Args:
            citation: Citation to resolve

        Returns:
            List of match candidates ordered by relevance
        """
        # Skip if citation already has DOI
        if citation.doi:
            logger.debug(f'Citation already has DOI: {citation.doi}')
            return []

        # Build query
        params = self._build_query(citation)
        if not params.get('query'):
            logger.warning(
                f'Cannot build Crossref query for citation: {citation.title or "untitled"}'
            )
            return []

        # Make API request
        logger.debug(
            f'Resolving citation via Crossref: {citation.title[:50] if citation.title else "untitled"}'
        )
        response = await self._rate_limited_request(params)

        if not response or 'message' not in response:
            logger.warning('Empty or invalid Crossref response')
            return []

        # Parse results
        message = response['message']
        items = message.get('items', [])

        if not items:
            logger.debug('No matches found in Crossref')
            return []

        candidates = [self._parse_work(work) for work in items]
        logger.info(
            f'Found {len(candidates)} Crossref matches for: '
            f'{citation.title[:50] if citation.title else "untitled"}'
        )

        return candidates

    async def batch_resolve(
        self, citations: list[Citation]
    ) -> dict[Citation, list[MatchCandidate]]:
        """
        Resolve multiple citations in batch.

        Args:
            citations: List of citations to resolve

        Returns:
            Dict mapping each citation to its match candidates
        """
        logger.info(f'Batch resolving {len(citations)} citations via Crossref')

        results = {}

        # Process citations concurrently with rate limiting
        tasks = [self.resolve_citation(citation) for citation in citations]
        matches_list = await asyncio.gather(*tasks, return_exceptions=True)

        for citation, matches in zip(citations, matches_list):  # noqa: B905
            if isinstance(matches, Exception):
                logger.error(
                    f'Error resolving citation {citation.title[:50] if citation.title else "untitled"}: {matches}'
                )
                results[citation] = []
            else:
                results[citation] = matches

        # Log statistics
        total_matches = sum(len(matches) for matches in results.values())
        logger.info(
            f'Batch resolution complete: {len(results)} citations processed, '
            f'{total_matches} total matches found'
        )
        self._log_stats()

        return results

    def _log_stats(self) -> None:
        """Log current statistics."""
        cache_hit_rate = (
            self._stats['cache_hits']
            / (self._stats['cache_hits'] + self._stats['cache_misses'])
            if (self._stats['cache_hits'] + self._stats['cache_misses']) > 0
            else 0.0
        )

        logger.info(
            f'Crossref stats: API calls={self._stats["api_calls"]}, '
            f'cache_hit_rate={cache_hit_rate:.1%}, '
            f'errors={self._stats["errors"]}, '
            f'retries={self._stats["retries"]}'
        )

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        return self._stats.copy()

    def clear_cache(self, older_than_days: int | None = None) -> int:
        """
        Clear cache entries.

        Args:
            older_than_days: Only clear entries older than this many days

        Returns:
            Number of entries deleted
        """
        if not self.enable_caching:
            return 0

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            if older_than_days is not None:
                cutoff_time = time.time() - (older_than_days * 86400)
                cursor.execute(
                    'DELETE FROM crossref_cache WHERE timestamp < ?', (cutoff_time,)
                )
            else:
                cursor.execute('DELETE FROM crossref_cache')

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f'Cleared {deleted} Crossref cache entries')
            return deleted
        except Exception as e:
            logger.error(f'Error clearing cache: {e}')
            return 0
