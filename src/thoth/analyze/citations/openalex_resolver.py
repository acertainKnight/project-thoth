"""
OpenAlex API resolver for citation matching and enrichment.

OpenAlex provides better fuzzy matching than Crossref and comprehensive metadata
for academic papers. This resolver implements async HTTP requests with rate limiting,
error handling, and match candidate scoring.
"""

import asyncio
import time
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from thoth.utilities.schemas import Citation


class MatchCandidate(BaseModel):
    """Represents a potential match for a citation from OpenAlex."""

    openalex_id: str | None = Field(
        default=None, description='OpenAlex ID (e.g., W1234567890)'
    )
    doi: str | None = Field(default=None, description='DOI of the matched paper')
    title: str | None = Field(default=None, description='Title of the matched paper')
    authors: list[str] | None = Field(default=None, description='List of author names')
    year: int | None = Field(default=None, description='Publication year')
    venue: str | None = Field(default=None, description='Publication venue/journal')
    abstract: str | None = Field(default=None, description='Paper abstract')
    citation_count: int | None = Field(default=None, description='Number of citations')
    confidence_score: float = Field(
        default=0.0, description='Match confidence score (0-1)'
    )
    url: str | None = Field(default=None, description='OpenAlex URL')
    pdf_url: str | None = Field(default=None, description='Open access PDF URL')
    is_open_access: bool | None = Field(default=None, description='Open access status')
    fields_of_study: list[str] | None = Field(
        default=None, description='Academic fields'
    )

    def to_citation(self) -> Citation:
        """Convert match candidate to Citation object."""
        return Citation(
            title=self.title,
            authors=self.authors,
            year=self.year,
            doi=self.doi,
            venue=self.venue,
            abstract=self.abstract,
            citation_count=self.citation_count,
            url=self.url,
            pdf_url=self.pdf_url,
            is_open_access=self.is_open_access,
            fields_of_study=self.fields_of_study,
            backup_id=f'openalex:{self.openalex_id}' if self.openalex_id else None,
        )


class OpenAlexResolver:
    """
    Async OpenAlex API resolver for citation matching and enrichment.

    Features:
    - Async HTTP requests with httpx
    - Configurable rate limiting (default: 10 req/sec)
    - Exponential backoff with retries
    - Query construction with title and year filtering
    - Response parsing with confidence scoring
    - Batch resolution support
    """

    BASE_URL = 'https://api.openalex.org'

    def __init__(
        self,
        email: str | None = None,
        requests_per_second: float = 10.0,
        max_retries: int = 3,
        timeout: int = 30,
        backoff_factor: float = 2.0,
        max_backoff: float = 60.0,
    ):
        """
        Initialize OpenAlex resolver.

        Args:
            email: Email for polite pool (gets 10x higher rate limit)
            requests_per_second: Rate limit for API requests
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            backoff_factor: Exponential backoff multiplier
            max_backoff: Maximum backoff time in seconds
        """
        self.email = email
        self.requests_per_second = requests_per_second
        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff

        # Rate limiting state
        self._last_request_time = 0.0
        self._min_interval = 1.0 / requests_per_second
        self._rate_lock: Optional[asyncio.Lock] = None  # Lazy init to avoid event loop binding

        # Statistics
        self._requests_made = 0
        self._matches_found = 0
        self._rate_limit_hits = 0

        logger.info(
            f'Initialized OpenAlex resolver with rate limit: {requests_per_second} req/sec'
            + (f', polite pool email: {email}' if email else '')
        )

    def _get_rate_lock(self) -> asyncio.Lock:
        """Get or create the rate limit lock (lazy init to avoid event loop binding)."""
        if self._rate_lock is None:
            self._rate_lock = asyncio.Lock()
        return self._rate_lock

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        async with self._get_rate_lock():
            current_time = time.monotonic()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self._min_interval:
                sleep_time = self._min_interval - time_since_last
                logger.debug(f'Rate limiting: sleeping {sleep_time:.3f}s')
                await asyncio.sleep(sleep_time)

            self._last_request_time = time.monotonic()

    def _build_search_query(self, citation: Citation) -> dict[str, Any] | None:
        """
        Build OpenAlex search query parameters from citation.

        Args:
            citation: Citation to search for

        Returns:
            Query parameters dict or None if insufficient info
        """
        if not citation.title:
            logger.warning('Cannot build query without title')
            return None

        # Start with title search
        query_parts = [f'title.search:{quote(citation.title)}']

        # Add year filter if available (within ±1 year for fuzzy matching)
        if citation.year:
            year_min = citation.year - 1
            year_max = citation.year + 1
            query_parts.append(f'publication_year:{year_min}-{year_max}')

        # Combine filters
        filter_str = ','.join(query_parts)

        params = {
            'filter': filter_str,
            'per-page': 5,  # Get top 5 matches
            'select': ','.join(
                [
                    'id',
                    'doi',
                    'title',
                    'display_name',
                    'authorships',
                    'publication_year',
                    'primary_location',
                    'open_access',
                    'cited_by_count',
                    'abstract_inverted_index',
                    'topics',
                ]
            ),
        }

        # Add polite pool email if available
        if self.email:
            params['mailto'] = self.email

        return params

    def _parse_response(
        self, data: dict[str, Any], citation: Citation
    ) -> list[MatchCandidate]:
        """
        Parse OpenAlex API response into match candidates.

        Args:
            data: Raw API response JSON
            citation: Original citation for scoring

        Returns:
            List of match candidates with confidence scores
        """
        if not data or 'results' not in data:
            return []

        candidates = []

        for result in data['results']:
            try:
                candidate = self._parse_single_work(result)

                # Calculate confidence score
                candidate.confidence_score = self._calculate_confidence(
                    candidate, citation
                )

                candidates.append(candidate)

            except Exception as e:
                logger.warning(f'Failed to parse OpenAlex result: {e}')
                continue

        # Sort by confidence score
        candidates.sort(key=lambda x: x.confidence_score, reverse=True)

        return candidates

    def _parse_single_work(self, work: dict[str, Any]) -> MatchCandidate:
        """Parse a single OpenAlex work into a MatchCandidate."""
        # Extract OpenAlex ID (format: https://openalex.org/W1234567890)
        openalex_id = None
        if work.get('id'):
            openalex_id = work['id'].split('/')[-1]

        # Extract authors
        authors = []
        if work.get('authorships'):
            for authorship in work['authorships']:
                if authorship.get('author') and authorship['author'].get(
                    'display_name'
                ):
                    authors.append(authorship['author']['display_name'])

        # Extract venue from primary location
        venue = None
        if work.get('primary_location') and work['primary_location'].get('source'):
            venue = work['primary_location']['source'].get('display_name')

        # Extract abstract from inverted index
        abstract = None
        if work.get('abstract_inverted_index'):
            abstract = self._reconstruct_abstract(work['abstract_inverted_index'])

        # Extract PDF URL from open access
        pdf_url = None
        is_oa = False
        if work.get('open_access'):
            is_oa = work['open_access'].get('is_oa', False)
            pdf_url = work['open_access'].get('oa_url')

        # Extract fields of study from topics
        fields = []
        if work.get('topics'):
            for topic in work['topics']:
                if topic.get('display_name'):
                    fields.append(topic['display_name'])

        return MatchCandidate(
            openalex_id=openalex_id,
            doi=work.get('doi'),
            title=work.get('display_name') or work.get('title'),
            authors=authors if authors else None,
            year=work.get('publication_year'),
            venue=venue,
            abstract=abstract,
            citation_count=work.get('cited_by_count'),
            url=work.get('id'),  # Full OpenAlex URL
            pdf_url=pdf_url,
            is_open_access=is_oa,
            fields_of_study=fields if fields else None,
        )

    def _reconstruct_abstract(self, inverted_index: dict[str, list[int]]) -> str:
        """
        Reconstruct abstract text from OpenAlex inverted index format.

        Args:
            inverted_index: Dict mapping words to position lists

        Returns:
            Reconstructed abstract text
        """
        if not inverted_index:
            return ''

        # Build list of (position, word) tuples
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))

        # Sort by position and join
        word_positions.sort(key=lambda x: x[0])
        return ' '.join(word for _, word in word_positions)

    def _calculate_confidence(
        self, candidate: MatchCandidate, citation: Citation
    ) -> float:
        """
        Calculate confidence score for a match candidate.

        Scoring factors:
        - Title similarity (most important)
        - Year match
        - Author overlap
        - DOI match (if available)

        Args:
            candidate: Match candidate from OpenAlex
            citation: Original citation

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.0

        # DOI match is definitive
        if citation.doi and candidate.doi:
            if citation.doi.lower() == candidate.doi.lower():
                return 1.0

        # Title similarity (0.5 weight)
        if citation.title and candidate.title:
            title_sim = self._string_similarity(
                citation.title.lower(), candidate.title.lower()
            )
            score += title_sim * 0.5

        # Year match (0.2 weight)
        if citation.year and candidate.year:
            if citation.year == candidate.year:
                score += 0.2
            elif abs(citation.year - candidate.year) == 1:
                score += 0.1  # Partial credit for ±1 year

        # Author overlap (0.3 weight)
        if citation.authors and candidate.authors:
            author_overlap = self._calculate_author_overlap(
                citation.authors, candidate.authors
            )
            score += author_overlap * 0.3

        return min(score, 1.0)

    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate simple string similarity using character overlap.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score between 0 and 1
        """
        if not s1 or not s2:
            return 0.0

        # Remove common words and punctuation
        for word in ['the', 'a', 'an', 'of', 'and', 'in', 'on', 'at', 'to']:
            s1 = s1.replace(f' {word} ', ' ')
            s2 = s2.replace(f' {word} ', ' ')

        s1 = ''.join(c for c in s1 if c.isalnum() or c.isspace())
        s2 = ''.join(c for c in s2 if c.isalnum() or c.isspace())

        # Calculate character overlap (Jaccard similarity)
        set1 = set(s1.split())
        set2 = set(s2.split())

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _calculate_author_overlap(
        self, authors1: list[str], authors2: list[str]
    ) -> float:
        """
        Calculate author overlap score.

        Args:
            authors1: First author list
            authors2: Second author list

        Returns:
            Overlap score between 0 and 1
        """
        if not authors1 or not authors2:
            return 0.0

        # Normalize author names (last name matching)
        def get_last_name(name: str) -> str:
            parts = name.strip().split()
            return parts[-1].lower() if parts else ''

        last_names1 = {get_last_name(a) for a in authors1}
        last_names2 = {get_last_name(a) for a in authors2}

        intersection = len(last_names1 & last_names2)
        min_size = min(len(last_names1), len(last_names2))

        return intersection / min_size if min_size > 0 else 0.0

    async def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Make async HTTP request to OpenAlex API with retries.

        Args:
            endpoint: API endpoint (e.g., '/works')
            params: Query parameters

        Returns:
            JSON response or None on failure
        """
        url = f'{self.BASE_URL}{endpoint}'

        for attempt in range(self.max_retries):
            try:
                # Enforce rate limiting
                await self._enforce_rate_limit()

                # Make request
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.debug(
                        f'OpenAlex request: {endpoint} (attempt {attempt + 1})'
                    )
                    response = await client.get(url, params=params)

                    self._requests_made += 1

                    # Handle rate limiting
                    if response.status_code == 429:
                        self._rate_limit_hits += 1
                        retry_after = int(response.headers.get('Retry-After', 5))
                        retry_after = min(retry_after, self.max_backoff)
                        logger.warning(
                            f'Rate limit hit (429). Retrying after {retry_after}s'
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f'HTTP error {e.response.status_code} on attempt {attempt + 1}: {e}'
                )
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    # Server error - retry with backoff
                    backoff = min(self.backoff_factor**attempt, self.max_backoff)
                    await asyncio.sleep(backoff)
                    continue
                else:
                    # Client error or final retry - give up
                    return None

            except httpx.RequestError as e:
                logger.warning(f'Request error on attempt {attempt + 1}: {e}')
                if attempt < self.max_retries - 1:
                    backoff = min(self.backoff_factor**attempt, self.max_backoff)
                    await asyncio.sleep(backoff)
                    continue
                else:
                    return None

            except Exception as e:
                logger.error(f'Unexpected error: {e}')
                return None

        return None

    async def resolve_citation(self, citation: Citation) -> list[MatchCandidate]:
        """
        Resolve a single citation to OpenAlex match candidates.

        Args:
            citation: Citation to resolve

        Returns:
            List of match candidates sorted by confidence
        """
        # Build query
        params = self._build_search_query(citation)
        if not params:
            logger.debug(f'Skipping citation without title: {citation.text or "N/A"}')
            return []

        # Make request
        data = await self._make_request('/works', params)
        if not data:
            return []

        # Parse response
        candidates = self._parse_response(data, citation)

        if candidates:
            self._matches_found += 1
            title_preview = citation.title[:50] if citation.title else 'Unknown'
            logger.debug(
                f'Found {len(candidates)} matches for "{title_preview}..." '
                f'(best score: {candidates[0].confidence_score:.2f})'
            )

        return candidates

    async def batch_resolve(
        self, citations: list[Citation]
    ) -> dict[Citation, list[MatchCandidate]]:
        """
        Resolve multiple citations in parallel (respecting rate limits).

        Args:
            citations: List of citations to resolve

        Returns:
            Dictionary mapping citations to their match candidates
        """
        if not citations:
            return {}

        logger.info(f'Batch resolving {len(citations)} citations with OpenAlex')

        # Create tasks for parallel execution
        tasks = [self.resolve_citation(citation) for citation in citations]

        # Execute with rate limiting
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result mapping
        resolution_map = {}
        for citation, result in zip(citations, results):  # noqa: B905
            if isinstance(result, Exception):
                logger.error(f'Error resolving citation: {result}')
                resolution_map[citation] = []
            else:
                resolution_map[citation] = result

        # Log statistics
        success_rate = self._matches_found / len(citations) * 100 if citations else 0
        logger.info(
            f'OpenAlex batch resolution complete: '
            f'{self._matches_found}/{len(citations)} citations matched ({success_rate:.1f}%), '
            f'{self._requests_made} API requests, '
            f'{self._rate_limit_hits} rate limit hits'
        )

        return resolution_map

    def get_statistics(self) -> dict[str, Any]:
        """Get resolver statistics."""
        return {
            'requests_made': self._requests_made,
            'matches_found': self._matches_found,
            'rate_limit_hits': self._rate_limit_hits,
            'requests_per_second': self.requests_per_second,
        }
