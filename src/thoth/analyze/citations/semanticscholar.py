"""
Citation utilities for interacting with Semantic Scholar API.
"""

import hashlib
import json
import sqlite3
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from thoth.utilities.schemas import Citation


class SemanticScholarAPI:
    """Client for interacting with Semantic Scholar API to retrieve citation metadata."""  # noqa: W505

    def __init__(
        self,
        base_url: str = 'https://api.semanticscholar.org/graph/v1',
        api_key: str | None = None,
        timeout: int = 10,
        delay_seconds: float = 1.0,
        max_retries: int = 3,  # Reduced from 9 to 3 for faster failures
        batch_size: int = 100,
        enable_caching: bool = True,
        max_backoff_seconds: float = 30.0,  # Cap backoff at 30 seconds
        backoff_multiplier: float = 1.5,  # Gentler than 2.0
        cache_dir: str | None = None,  # Directory for persistent cache
        circuit_breaker_threshold: int = 10,  # Failures before circuit opens
        circuit_breaker_timeout: float = 300.0,  # 5 min cooldown before retry
    ):
        """
        Initialize Semantic Scholar API client.

        Args:
            base_url: Base URL for the Semantic Scholar API.
            api_key: Semantic Scholar API key for authentication (recommended for higher rate limits).
            timeout: Timeout for API requests in seconds.
            delay_seconds: Delay between API requests to avoid rate limiting.
            max_retries: Maximum number of retry attempts for failed requests.
            batch_size: Number of citations to process in each batch.
            enable_caching: Whether to enable caching of API responses.
            max_backoff_seconds: Maximum backoff time to prevent excessive delays.
            backoff_multiplier: Multiplier for exponential backoff (gentler than 2.0).
            cache_dir: Directory for persistent SQLite cache (default: ./cache/semanticscholar).
            circuit_breaker_threshold: Number of consecutive failures before circuit opens.
            circuit_breaker_timeout: Seconds to wait before attempting recovery after circuit opens.
        """  # noqa: W505
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.enable_caching = enable_caching
        self.max_backoff_seconds = max_backoff_seconds
        self.backoff_multiplier = backoff_multiplier
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # In-memory caches (LRU-style)
        self._doi_cache: dict[str, Any] = {}
        self._arxiv_cache: dict[str, Any] = {}
        self._cache_size = 1000  # Maximum number of items to cache in memory

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at = 0.0

        # Cache metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._api_calls = 0

        # Persistent cache setup
        self.cache_dir = (
            Path(cache_dir) if cache_dir else Path('./cache/semanticscholar')
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'api_cache.db'
        self._init_persistent_cache()

        self.client = httpx.Client(timeout=timeout)
        self.last_request_time = 0

        if not api_key:
            logger.warning(
                'No Semantic Scholar API key provided. Using public API access with lower rate limits.'
            )

    def _init_persistent_cache(self) -> None:
        """Initialize SQLite persistent cache database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_data TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    endpoint TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON api_cache(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_endpoint ON api_cache(endpoint)
            """)
            conn.commit()
            conn.close()
            logger.info(f'Initialized persistent cache at {self.db_path}')
        except Exception as e:
            logger.error(f'Failed to initialize persistent cache: {e}')

    def _generate_cache_key(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> str:
        """Generate a unique cache key for an API request."""
        key_parts = [endpoint]
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        if json_data:
            key_parts.append(json.dumps(json_data, sort_keys=True))
        key_string = '|'.join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_from_persistent_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve data from persistent cache."""
        if not self.enable_caching:
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                'SELECT response_data FROM api_cache WHERE cache_key = ?', (cache_key,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                self._cache_hits += 1
                logger.debug(
                    f'Cache HIT for key {cache_key[:16]}... (Hit rate: {self.get_cache_hit_rate():.1%})'
                )
                return json.loads(row[0])

            self._cache_misses += 1
            return None
        except Exception as e:
            logger.error(f'Error reading from persistent cache: {e}')
            return None

    def _save_to_persistent_cache(
        self, cache_key: str, endpoint: str, data: dict[str, Any]
    ) -> None:
        """Save data to persistent cache."""
        if not self.enable_caching or not data:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO api_cache (cache_key, response_data, timestamp, endpoint)
                VALUES (?, ?, ?, ?)
            """,
                (cache_key, json.dumps(data), time.time(), endpoint),
            )
            conn.commit()
            conn.close()
            logger.debug(f'Saved to persistent cache: {cache_key[:16]}...')
        except Exception as e:
            logger.error(f'Error writing to persistent cache: {e}')

    def _check_circuit_breaker(self) -> bool:
        """
        Check circuit breaker state and attempt recovery if timeout has passed.

        Returns:
            bool: True if circuit is open (API calls blocked), False if closed.
        """
        if not self._circuit_open:
            return False

        # Check if cooldown period has elapsed
        time_since_opened = time.time() - self._circuit_opened_at
        if time_since_opened >= self.circuit_breaker_timeout:
            logger.info(
                f'Circuit breaker recovery attempt after {time_since_opened:.1f}s cooldown. '
                f'Resetting failure count and allowing API calls.'
            )
            self._circuit_open = False
            self._consecutive_failures = 0
            return False

        logger.warning(
            f'Circuit breaker OPEN - API calls blocked. '
            f'{self.circuit_breaker_timeout - time_since_opened:.1f}s remaining until recovery attempt. '
            f'Using cache-only mode.'
        )
        return True

    def _record_failure(self) -> None:
        """Record a failure and potentially open the circuit breaker."""
        self._consecutive_failures += 1
        logger.debug(
            f'Consecutive failures: {self._consecutive_failures}/{self.circuit_breaker_threshold}'
        )

        if (
            self._consecutive_failures >= self.circuit_breaker_threshold
            and not self._circuit_open
        ):
            self._circuit_open = True
            self._circuit_opened_at = time.time()
            logger.error(
                f'Circuit breaker OPENED after {self._consecutive_failures} consecutive failures. '
                f'Entering cache-only mode for {self.circuit_breaker_timeout}s. '
                f'This prevents further rate limit errors and API hammering.'
            )

    def _record_success(self) -> None:
        """Record a successful API call and reset failure counter."""
        if self._consecutive_failures > 0:
            logger.info(
                f'API call succeeded. Resetting failure count from {self._consecutive_failures} to 0.'
            )
        self._consecutive_failures = 0

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._cache_hits + self._cache_misses
        return self._cache_hits / total if total > 0 else 0.0

    def get_cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache and API statistics."""
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_hit_rate': self.get_cache_hit_rate(),
            'api_calls': self._api_calls,
            'consecutive_failures': self._consecutive_failures,
            'circuit_breaker_open': self._circuit_open,
            'circuit_breaker_threshold': self.circuit_breaker_threshold,
            'memory_cache_size': len(self._doi_cache) + len(self._arxiv_cache),
        }

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        method: str = 'GET',
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Make a request to the Semantic Scholar API with rate limiting and retries.

        Args:
            endpoint: API endpoint to call.
            params: API query parameters.
            method: HTTP method to use.
            json_data: JSON data for POST requests.

        Returns:
            dict | None: JSON response data or None if the request failed.

        Raises:
            httpx.HTTPError: If the request fails after retries.
        """
        # Generate cache key for this request
        cache_key = self._generate_cache_key(endpoint, params, json_data)

        # Check persistent cache first (works even with circuit breaker open)
        cached_response = self._get_from_persistent_cache(cache_key)
        if cached_response is not None:
            return cached_response

        # Check circuit breaker - if open, return None (cache miss handled above)
        if self._check_circuit_breaker():
            logger.warning(
                f'Circuit breaker OPEN - skipping API call to {endpoint}. '
                f'No cached data available. Consider using API key for higher rate limits.'
            )
            return None

        # Implement rate limiting with adaptive delay based on API key status
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        # Use shorter delays for authenticated requests
        effective_delay = (
            self.delay_seconds if not self.api_key else self.delay_seconds * 0.1
        )

        if time_since_last_request < effective_delay:
            sleep_time = effective_delay - time_since_last_request
            logger.debug(
                f'Rate limiting: sleeping for {sleep_time:.2f} seconds before request.'
            )
            time.sleep(sleep_time)

        # Prepare headers
        headers = {'Accept': 'application/json'}
        if json_data:
            headers['Content-Type'] = 'application/json'
        if self.api_key:
            headers['x-api-key'] = self.api_key

        # Prepare URL with parameters
        url = f'{self.base_url}/{endpoint}'
        if params and method == 'GET':
            url = f'{url}?{urllib.parse.urlencode(params)}'

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f'Making {method} request to Semantic Scholar API: {url} (Attempt {attempt + 1}/{self.max_retries + 1})'
                )

                if method == 'POST':
                    response = self.client.post(
                        url, headers=headers, json=json_data, params=params
                    )
                else:
                    response = self.client.get(url, headers=headers)

                self.last_request_time = time.time()
                response.raise_for_status()

                # Success! Record it, increment API call counter, and cache the result
                self._api_calls += 1
                self._record_success()
                result = response.json()
                self._save_to_persistent_cache(cache_key, endpoint, result)
                return result
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f'Semantic Scholar API request failed (Attempt {attempt + 1}/{self.max_retries + 1}): '
                    f'Status {e.response.status_code} - {e.response.text}'
                )
                if attempt < self.max_retries:
                    if e.response.status_code == 429:  # Too Many Requests
                        # Respect Retry-After header if present
                        retry_after_str = e.response.headers.get('Retry-After')
                        if retry_after_str:
                            try:
                                sleep_duration = min(
                                    int(retry_after_str), self.max_backoff_seconds
                                )
                                logger.info(
                                    f'Rate limit hit (429). Retrying after {sleep_duration} seconds (from Retry-After header).'
                                )
                            except ValueError:
                                # Use optimized exponential backoff
                                sleep_duration = min(
                                    effective_delay
                                    * (self.backoff_multiplier**attempt),
                                    self.max_backoff_seconds,
                                )
                                logger.info(
                                    f'Rate limit hit (429). Retrying after {sleep_duration:.2f} seconds (capped backoff).'
                                )
                        else:
                            # Use optimized exponential backoff with cap
                            sleep_duration = min(
                                effective_delay * (self.backoff_multiplier**attempt),
                                self.max_backoff_seconds,
                            )
                            logger.info(
                                f'Rate limit hit (429). Retrying after {sleep_duration:.2f} seconds (capped backoff).'
                            )
                        time.sleep(sleep_duration)
                        self._record_failure()
                    elif e.response.status_code >= 500:  # Server-side errors
                        sleep_duration = min(
                            effective_delay * (self.backoff_multiplier**attempt),
                            self.max_backoff_seconds,
                        )
                        logger.warning(
                            f'Server error ({e.response.status_code}). Retrying after {sleep_duration:.2f} seconds.'
                        )
                        time.sleep(sleep_duration)
                        self._record_failure()
                    else:  # Other client-side errors that might not be worth retrying or need different strategy
                        raise  # Re-raise immediately for other client errors
                else:
                    logger.error(
                        f'Failed to make Semantic Scholar API request after {self.max_retries + 1} attempts: {e}'
                    )
                    raise
            except httpx.RequestError as e:  # Includes network errors, timeouts etc.
                logger.warning(
                    f'Semantic Scholar API request failed due to network/request error (Attempt {attempt + 1}/{self.max_retries + 1}): {e}'
                )
                if attempt < self.max_retries:
                    sleep_duration = min(
                        effective_delay * (self.backoff_multiplier**attempt),
                        self.max_backoff_seconds,
                    )
                    logger.info(f'Retrying after {sleep_duration:.2f} seconds.')
                    time.sleep(sleep_duration)
                    self._record_failure()
                else:
                    logger.error(
                        f'Failed to make Semantic Scholar API request after {self.max_retries + 1} attempts due to network/request error: {e}'
                    )
                    raise
            except Exception as e:  # Catch any other unexpected errors
                logger.error(
                    f'An unexpected error occurred while processing Semantic Scholar API response (Attempt {attempt + 1}): {e}'
                )
                if attempt == self.max_retries:  # if it's the last attempt
                    raise  # Re-raise the caught exception
                # For unexpected errors, use capped backoff
                sleep_duration = min(
                    effective_delay * (self.backoff_multiplier**attempt),
                    self.max_backoff_seconds,
                )
                logger.info(
                    f'Retrying after {sleep_duration:.2f} seconds due to unexpected error.'
                )
                time.sleep(sleep_duration)
                self._record_failure()
        return None  # Should be unreachable if max_retries is handled correctly

    def _cached_paper_lookup_by_doi(
        self, doi: str, fields_str: str
    ) -> dict[str, Any] | None:
        """Lookup paper by DOI with caching.

        Args:
            doi: The DOI to look up.
            fields_str: Comma-separated list of fields to return.

        Returns:
            dict[str, Any] | None: The paper data or None if not found.
        """
        if not self.enable_caching:
            return self.paper_lookup_by_doi(doi, fields_str)

        cache_key = f'{doi}:{fields_str}'
        if cache_key in self._doi_cache:
            return self._doi_cache[cache_key]

        result = self.paper_lookup_by_doi(doi, fields_str)
        if result:
            # Implement LRU-like behavior by removing oldest items if cache is full
            if len(self._doi_cache) >= self._cache_size:
                self._doi_cache.pop(next(iter(self._doi_cache)))
            self._doi_cache[cache_key] = result
        return result

    def _cached_paper_lookup_by_arxiv(
        self, arxiv_id: str, fields_str: str
    ) -> dict[str, Any] | None:
        """Lookup paper by arXiv ID with caching.

        Args:
            arxiv_id: The arXiv ID to look up.
            fields_str: Comma-separated list of fields to return.

        Returns:
            dict[str, Any] | None: The paper data or None if not found.
        """
        if not self.enable_caching:
            return self.paper_lookup_by_arxiv(arxiv_id, fields_str)

        cache_key = f'{arxiv_id}:{fields_str}'
        if cache_key in self._arxiv_cache:
            return self._arxiv_cache[cache_key]

        result = self.paper_lookup_by_arxiv(arxiv_id, fields_str)
        if result:
            # Implement LRU-like behavior by removing oldest items if cache is full
            if len(self._arxiv_cache) >= self._cache_size:
                self._arxiv_cache.pop(next(iter(self._arxiv_cache)))
            self._arxiv_cache[cache_key] = result
        return result

    def paper_lookup_by_doi(
        self, doi: str, fields: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Look up a paper by DOI.

        Args:
            doi: The DOI of the paper to look up.
            fields: Specific fields to return in the response.

        Returns:
            dict | None: Paper metadata or None if not found.
        """
        if self.enable_caching:
            fields_str = ','.join(fields) if fields else ''
            return self._cached_paper_lookup_by_doi(doi, fields_str)

        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = f'paper/DOI:{doi}'
            return self._make_request(endpoint, params)
        except Exception as e:
            logger.error(f'Failed to look up paper by DOI {doi}: {e}')
            return None

    def paper_lookup_by_arxiv(
        self, arxiv_id: str, fields: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Look up a paper by arXiv ID.

        Args:
            arxiv_id: The arXiv ID of the paper to look up.
            fields: Specific fields to return in the response.

        Returns:
            dict | None: Paper metadata or None if not found.
        """
        if self.enable_caching:
            fields_str = ','.join(fields) if fields else ''
            return self._cached_paper_lookup_by_arxiv(arxiv_id, fields_str)

        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = f'paper/arXiv:{arxiv_id}'
            return self._make_request(endpoint, params)
        except Exception as e:
            logger.error(f'Failed to look up paper by arXiv ID {arxiv_id}: {e}')
            return None

    def paper_search(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Search for papers matching the query.

        Args:
            query: Search query (title, authors, etc.).
            fields: Specific fields to return in the response.
            limit: Maximum number of results to return.
            offset: Offset for pagination.

        Returns:
            list: List of papers matching the search criteria.
        """
        params = {
            'query': query,
            'limit': limit,
            'offset': offset,
        }
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = 'paper/search'
            response = self._make_request(endpoint, params)
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Failed to search papers with query '{query}': {e}")
            return []

    def paper_lookup_batch(
        self,
        paper_ids: list[str],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Look up multiple papers by their IDs in a single batch request.

        Args:
            paper_ids: List of paper IDs with prefixes (e.g., ["DOI:10.1234/xyz", "arXiv:1234.5678"]).
            fields: Specific fields to return in the response.

        Returns:
            list: List of paper metadata records.
        """  # noqa: W505
        if not paper_ids:
            return []

        # Split into batches if necessary
        all_results = []
        for i in range(0, len(paper_ids), self.batch_size):
            batch_ids = paper_ids[i : i + self.batch_size]
            batch_results = self._paper_lookup_batch_single(batch_ids, fields)
            all_results.extend(batch_results)

        return all_results

    def _paper_lookup_batch_single(
        self,
        paper_ids: list[str],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Look up a single batch of papers (internal method).

        Args:
            paper_ids: List of paper IDs (should be <= batch_size).
            fields: Specific fields to return in the response.

        Returns:
            list: List of paper metadata records.
        """
        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        try:
            # Convert the list to the required format for the Semantic Scholar API
            ids_payload = {'ids': paper_ids}

            response = self._make_request(
                'paper/batch', params=params, method='POST', json_data=ids_payload
            )

            if response and 'data' in response:
                # Filter out None results (papers not found)
                return [paper for paper in response['data'] if paper is not None]
            return []
        except Exception as e:
            logger.error(f'Failed to look up papers in batch: {e}')
            return []

    def author_search(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Search for authors matching the query.

        Args:
            query: Search query (author name).
            fields: Specific fields to return in the response.
            limit: Maximum number of results to return.
            offset: Offset for pagination.

        Returns:
            list: List of authors matching the search criteria.
        """
        params = {
            'query': query,
            'limit': limit,
            'offset': offset,
        }
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = 'author/search'
            response = self._make_request(endpoint, params)
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Failed to search authors with query '{query}': {e}")
            return []

    def update_citation_from_semantic_scholar(
        self, citation: Citation, paper_data: dict[str, Any]
    ) -> None:
        """
        Update a Citation object with data from Semantic Scholar.

        Args:
            citation: The Citation object to update.
            paper_data: Paper data from Semantic Scholar API.
        """
        if not paper_data:
            return

        # Update basic metadata
        if not citation.title and 'title' in paper_data:
            citation.title = paper_data['title']

        if (
            not citation.doi
            and 'externalIds' in paper_data
            and paper_data['externalIds']
            and 'DOI' in paper_data['externalIds']
        ):
            citation.doi = paper_data['externalIds']['DOI']

        # Update authors if available
        if not citation.authors and 'authors' in paper_data and paper_data['authors']:
            citation.authors = [
                author['name'] for author in paper_data['authors'] if 'name' in author
            ]

        # Update abstract
        if not citation.abstract and 'abstract' in paper_data:
            citation.abstract = paper_data['abstract']

        # Update journal information
        if not citation.journal and 'journal' in paper_data and paper_data['journal']:
            citation.journal = (
                paper_data['journal']['name']
                if 'name' in paper_data['journal']
                else None
            )

        # Update publication year
        if not citation.year and 'year' in paper_data and paper_data['year']:
            citation.year = paper_data['year']

        # Update publication venue
        if not citation.venue and 'venue' in paper_data:
            citation.venue = paper_data['venue']

        # Update URL
        if not citation.url and 'url' in paper_data:
            citation.url = paper_data['url']
        elif (
            not citation.url
            and 'openAccessPdf' in paper_data
            and paper_data['openAccessPdf']
        ):
            citation.url = paper_data['openAccessPdf']['url']

        # Update citation count
        if citation.citation_count is None and 'citationCount' in paper_data:
            citation.citation_count = paper_data['citationCount']

        # Update fields of study
        if not citation.fields_of_study and 'fieldsOfStudy' in paper_data:
            citation.fields_of_study = paper_data['fieldsOfStudy']

        # Update backup_id if arXiv ID is available and not already set
        if (
            not citation.backup_id
            and 'externalIds' in paper_data
            and paper_data['externalIds']
            and 'ArXiv' in paper_data['externalIds']
        ):
            citation.backup_id = f'arxiv:{paper_data["externalIds"]["ArXiv"]}'

        # Map any additional Semantic Scholar attributes to Citation if present
        if (
            'referenceCount' in paper_data
            and getattr(citation, 'reference_count', None) is None
        ):
            citation.reference_count = paper_data['referenceCount']
        if (
            'influentialCitationCount' in paper_data
            and getattr(citation, 'influential_citation_count', None) is None
        ):
            citation.influential_citation_count = paper_data['influentialCitationCount']
        if (
            'isOpenAccess' in paper_data
            and getattr(citation, 'is_open_access', None) is None
        ):
            citation.is_open_access = paper_data['isOpenAccess']
        if (
            's2FieldsOfStudy' in paper_data
            and getattr(citation, 's2_fields_of_study', None) is None
        ):
            s2_fields = paper_data['s2FieldsOfStudy']
            if s2_fields and isinstance(s2_fields[0], dict):
                citation.s2_fields_of_study = [
                    field.get('category')
                    for field in s2_fields
                    if field.get('category')
                ]
            else:
                # If it's already a list of strings, assign it directly
                citation.s2_fields_of_study = s2_fields

    def semantic_scholar_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Look up citations in Semantic Scholar and enhance with additional metadata using optimized batch processing.

        Args:
            citations: List of citations to enhance.

        Returns:
            list[Citation]: The citations with enhanced information from Semantic Scholar.
        """  # noqa: W505
        if not citations:
            return citations

        logger.info(
            f'Looking up {len(citations)} citations in Semantic Scholar using optimized batch processing'
        )

        # Fields to request from Semantic Scholar API
        fields = [
            'title',
            'abstract',
            'authors',
            'year',
            'venue',
            'journal',
            'url',
            'externalIds',
            'citationCount',
            'openAccessPdf',
            'fieldsOfStudy',
            'referenceCount',
            'influentialCitationCount',
            'isOpenAccess',
            's2FieldsOfStudy',
        ]

        # Group citations by lookup strategy for optimal batching
        doi_citations = []
        arxiv_citations = []
        title_search_citations = []
        citation_lookup_map = {}  # Maps paper_id -> list of citations

        for citation in citations:
            if citation.doi:
                paper_id = f'DOI:{citation.doi}'
                doi_citations.append(paper_id)
                if paper_id not in citation_lookup_map:
                    citation_lookup_map[paper_id] = []
                citation_lookup_map[paper_id].append(citation)
            elif citation.backup_id and citation.backup_id.startswith('arxiv:'):
                arxiv_id = citation.backup_id.split(':', 1)[1]
                paper_id = f'arXiv:{arxiv_id}'
                arxiv_citations.append(paper_id)
                if paper_id not in citation_lookup_map:
                    citation_lookup_map[paper_id] = []
                citation_lookup_map[paper_id].append(citation)
            elif citation.title:
                title_search_citations.append(citation)

        # Batch process DOI and arXiv lookups
        batch_paper_ids = doi_citations + arxiv_citations
        enhanced_count = 0

        if batch_paper_ids:
            logger.info(
                f'Batch processing {len(batch_paper_ids)} citations with identifiers (DOI/arXiv)'
            )
            try:
                batch_results = self.paper_lookup_batch(batch_paper_ids, fields)

                # Map results back to citations
                for paper_data in batch_results:
                    if not paper_data:
                        continue

                    # Find the paper ID that matches this result
                    paper_id = None

                    # Check DOI match
                    if paper_data.get('externalIds'):
                        if 'DOI' in paper_data['externalIds']:
                            paper_id = f'DOI:{paper_data["externalIds"]["DOI"]}'
                        elif 'ArXiv' in paper_data['externalIds']:
                            paper_id = f'arXiv:{paper_data["externalIds"]["ArXiv"]}'

                    if paper_id and paper_id in citation_lookup_map:
                        for citation in citation_lookup_map[paper_id]:
                            self.update_citation_from_semantic_scholar(
                                citation, paper_data
                            )
                            enhanced_count += 1

            except Exception as e:
                logger.error(f'Error in batch lookup: {e}')
                # Fall back to individual lookups for batch_paper_ids
                for paper_id in batch_paper_ids:
                    try:
                        if paper_id.startswith('DOI:'):
                            doi = paper_id[4:]  # Remove "DOI:" prefix
                            paper_data = self.paper_lookup_by_doi(doi, fields)
                        elif paper_id.startswith('arXiv:'):
                            arxiv_id = paper_id[6:]  # Remove "arXiv:" prefix
                            paper_data = self.paper_lookup_by_arxiv(arxiv_id, fields)
                        else:
                            continue

                        if paper_data and paper_id in citation_lookup_map:
                            for citation in citation_lookup_map[paper_id]:
                                self.update_citation_from_semantic_scholar(
                                    citation, paper_data
                                )
                                enhanced_count += 1
                    except Exception as individual_e:
                        logger.warning(
                            f'Failed individual lookup for {paper_id}: {individual_e}'
                        )

        # Handle title-based searches (these cannot be batched easily)
        if title_search_citations:
            logger.info(
                f'Processing {len(title_search_citations)} citations via title search'
            )
            for citation in title_search_citations:
                try:
                    # Use exact title search with quotes
                    search_results = self.paper_search(
                        f'"{citation.title}"', fields, limit=1
                    )
                    if search_results:
                        paper_data = search_results[0]
                        self.update_citation_from_semantic_scholar(citation, paper_data)
                        enhanced_count += 1
                except Exception as e:
                    logger.warning(
                        f'Error enhancing citation via title search "{citation.title}": {e}'
                    )

        # Log comprehensive statistics
        stats = self.get_cache_stats()
        logger.info(
            f'Successfully enhanced {enhanced_count} out of {len(citations)} citations with Semantic Scholar. '
            f'Cache stats: {stats["cache_hit_rate"]:.1%} hit rate '
            f'({stats["cache_hits"]} hits, {stats["cache_misses"]} misses), '
            f'{stats["api_calls"]} API calls made, '
            f'circuit breaker: {"OPEN" if stats["circuit_breaker_open"] else "closed"}'
        )
        return citations

    def clear_cache(self, older_than_days: int | None = None) -> int:
        """
        Clear persistent cache entries.

        Args:
            older_than_days: Only clear entries older than this many days. If None,
            clears all.

        Returns:
            int: Number of entries deleted.
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            if older_than_days is not None:
                cutoff_time = time.time() - (older_than_days * 86400)
                cursor.execute(
                    'DELETE FROM api_cache WHERE timestamp < ?', (cutoff_time,)
                )
            else:
                cursor.execute('DELETE FROM api_cache')

            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f'Cleared {deleted} cache entries from persistent cache')
            return deleted
        except Exception as e:
            logger.error(f'Error clearing cache: {e}')
            return 0

    def close(self) -> None:
        """Close the HTTP client and log final statistics."""
        stats = self.get_cache_stats()
        logger.info(
            f'Closing Semantic Scholar API client. Final stats: '
            f'{stats["api_calls"]} API calls, '
            f'{stats["cache_hit_rate"]:.1%} cache hit rate '
            f'({stats["cache_hits"]} hits / {stats["cache_misses"]} misses), '
            f'{stats["consecutive_failures"]} consecutive failures at close time'
        )
        self.client.close()
