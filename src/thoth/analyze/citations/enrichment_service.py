"""
Citation Enrichment Service

This service enriches citations after resolution by fetching full metadata from
multiple academic APIs (Crossref, OpenAlex, Semantic Scholar). It prioritizes
sources based on data quality and availability, merging metadata intelligently.

Key Features:
- Multi-source enrichment (Crossref, OpenAlex, Semantic Scholar)
- Async HTTP requests with proper error handling
- Intelligent metadata merging with source prioritization
- Batch processing support
- Comprehensive logging of enrichment sources
"""

import asyncio
from typing import Any, Dict, List, Optional  # noqa: UP035

import httpx
from loguru import logger

from thoth.analyze.citations.resolution_types import APISource, ResolutionResult
from thoth.utilities.schemas.citations import Citation


class CitationEnrichmentService:
    """
    Service for enriching citations with full metadata from multiple APIs.

    This service takes resolved citations (with DOI, OpenAlex ID, or S2 ID) and
    fetches comprehensive metadata including abstracts, citation counts, and
    open access information.
    """

    # API endpoints
    CROSSREF_BASE = 'https://api.crossref.org/works'
    OPENALEX_BASE = 'https://api.openalex.org'
    S2_BASE = 'https://api.semanticscholar.org/graph/v1'

    def __init__(
        self,
        crossref_api_key: Optional[str] = None,  # noqa: UP007
        openalex_email: Optional[str] = None,  # noqa: UP007
        s2_api_key: Optional[str] = None,  # noqa: UP007
        timeout: int = 30,
        max_retries: int = 3,
        requests_per_second: float = 10.0,
    ):
        """
        Initialize enrichment service.

        Args:
            crossref_api_key: Crossref Plus API key for higher rate limits
            openalex_email: Email for OpenAlex polite pool (10x higher rate limit)
            s2_api_key: Semantic Scholar API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts per request
            requests_per_second: Rate limit for API requests
        """
        self.crossref_api_key = crossref_api_key
        self.openalex_email = openalex_email
        self.s2_api_key = s2_api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.requests_per_second = requests_per_second

        # Rate limiting
        self._min_interval = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._rate_lock = asyncio.Lock()

        # HTTP client (created on first use)
        self._client: Optional[httpx.AsyncClient] = None  # noqa: UP007

        # Statistics
        self._stats = {
            'total_enriched': 0,
            'crossref_enrichments': 0,
            'openalex_enrichments': 0,
            's2_enrichments': 0,
            'errors': 0,
            'retries': 0,
        }

        logger.info(
            f'Initialized CitationEnrichmentService with rate_limit={requests_per_second} req/s'
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            headers = {
                'User-Agent': 'ThothResearchAssistant/1.0 (mailto:research@example.com)'
            }
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info(f'Enrichment service closed. Stats: {self._stats}')

    async def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        async with self._rate_lock:
            import time

            current_time = time.monotonic()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self._min_interval:
                sleep_time = self._min_interval - time_since_last
                await asyncio.sleep(sleep_time)

            self._last_request_time = time.monotonic()

    async def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,  # noqa: UP006, UP007
    ) -> Optional[Dict[str, Any]]:  # noqa: UP006, UP007
        """
        Make HTTP request with retries and error handling.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers

        Returns:
            JSON response or None on failure
        """
        client = await self._get_client()

        for attempt in range(self.max_retries):
            try:
                # Enforce rate limiting
                await self._enforce_rate_limit()

                # Make request
                response = await client.get(url, params=params, headers=headers or {})

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(
                        f'Rate limit hit. Retrying after {retry_after}s (attempt {attempt + 1})'
                    )
                    await asyncio.sleep(retry_after)
                    self._stats['retries'] += 1
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f'HTTP error {e.response.status_code} on attempt {attempt + 1}: {e}'
                )
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    # Server error - retry with exponential backoff
                    backoff = min(2**attempt, 30)
                    await asyncio.sleep(backoff)
                    self._stats['retries'] += 1
                    continue
                self._stats['errors'] += 1
                return None

            except httpx.RequestError as e:
                logger.warning(f'Request error on attempt {attempt + 1}: {e}')
                if attempt < self.max_retries - 1:
                    backoff = min(2**attempt, 30)
                    await asyncio.sleep(backoff)
                    self._stats['retries'] += 1
                    continue
                self._stats['errors'] += 1
                return None

            except Exception as e:
                logger.error(f'Unexpected error: {e}')
                self._stats['errors'] += 1
                return None

        return None

    async def _fetch_crossref_metadata(self, doi: str) -> Optional[Dict[str, Any]]:  # noqa: UP006, UP007
        """
        Fetch metadata from Crossref API.

        Args:
            doi: DOI to lookup

        Returns:
            Crossref work data or None
        """
        url = f'{self.CROSSREF_BASE}/{doi}'
        headers = {}

        if self.crossref_api_key:
            headers['Crossref-Plus-API-Token'] = f'Bearer {self.crossref_api_key}'

        logger.debug(f'Fetching Crossref metadata for DOI: {doi}')
        response = await self._make_request(url, headers=headers)

        if response and 'message' in response:
            return response['message']
        return None

    async def _fetch_openalex_metadata(
        self, openalex_id: str
    ) -> Optional[Dict[str, Any]]:  # noqa: UP006, UP007
        """
        Fetch metadata from OpenAlex API.

        Args:
            openalex_id: OpenAlex ID (e.g., W1234567890)

        Returns:
            OpenAlex work data or None
        """
        # Construct full URL if needed
        if not openalex_id.startswith('http'):
            url = f'{self.OPENALEX_BASE}/works/{openalex_id}'
        else:
            url = openalex_id

        params = {}
        if self.openalex_email:
            params['mailto'] = self.openalex_email

        logger.debug(f'Fetching OpenAlex metadata for ID: {openalex_id}')
        return await self._make_request(url, params=params)

    async def _fetch_s2_metadata(self, paper_id: str) -> Optional[Dict[str, Any]]:  # noqa: UP006, UP007
        """
        Fetch metadata from Semantic Scholar API.

        Args:
            paper_id: Semantic Scholar paper ID or identifier (DOI:xxx, ARXIV:yyy, etc.)

        Returns:
            Semantic Scholar paper data or None
        """
        url = f'{self.S2_BASE}/paper/{paper_id}'

        # Request comprehensive fields
        params = {
            'fields': ','.join(
                [
                    'title',
                    'abstract',
                    'authors',
                    'year',
                    'venue',
                    'journal',
                    'citationCount',
                    'influentialCitationCount',
                    'referenceCount',
                    'fieldsOfStudy',
                    's2FieldsOfStudy',
                    'openAccessPdf',
                    'isOpenAccess',
                    'externalIds',
                    'url',
                ]
            )
        }

        headers = {}
        if self.s2_api_key:
            headers['x-api-key'] = self.s2_api_key

        logger.debug(f'Fetching Semantic Scholar metadata for ID: {paper_id}')
        return await self._make_request(url, params=params, headers=headers)

    def _merge_metadata(
        self,
        citation: Citation,
        metadata_dict: Dict[str, Any],
        source: APISource,  # noqa: UP006
    ) -> Citation:
        """
        Merge metadata from API into Citation object.

        Only updates fields that are None in the Citation. This preserves
        existing data and prevents overwriting with lower-quality data.

        Args:
            citation: Citation to enrich
            metadata_dict: Metadata from API
            source: API source

        Returns:
            Enriched Citation
        """
        if not metadata_dict:
            return citation

        if source == APISource.CROSSREF:
            # Crossref-specific field mappings
            if citation.title is None and 'title' in metadata_dict:
                citation.title = (
                    metadata_dict['title'][0] if metadata_dict['title'] else None
                )

            if citation.abstract is None and 'abstract' in metadata_dict:
                citation.abstract = metadata_dict['abstract']

            if citation.authors is None and 'author' in metadata_dict:
                authors = []
                for author in metadata_dict['author']:
                    if 'given' in author and 'family' in author:
                        authors.append(f'{author["given"]} {author["family"]}')
                    elif 'family' in author:
                        authors.append(author['family'])
                citation.authors = authors if authors else None

            if citation.year is None:
                # Try multiple date fields
                for date_field in ['published-print', 'published-online', 'created']:
                    if date_field in metadata_dict:
                        date_parts = metadata_dict[date_field].get('date-parts', [[]])
                        if date_parts and len(date_parts[0]) > 0:
                            citation.year = date_parts[0][0]
                            break

            if citation.journal is None and 'container-title' in metadata_dict:
                citation.journal = (
                    metadata_dict['container-title'][0]
                    if metadata_dict['container-title']
                    else None
                )

            if citation.volume is None:
                citation.volume = metadata_dict.get('volume')

            if citation.issue is None:
                citation.issue = metadata_dict.get('issue')

            if citation.pages is None:
                citation.pages = metadata_dict.get('page')

            if citation.url is None:
                citation.url = metadata_dict.get('URL')

            if citation.citation_count is None:
                citation.citation_count = metadata_dict.get('is-referenced-by-count')

            # Check for open access PDFs
            if citation.pdf_url is None:
                for link in metadata_dict.get('link', []):
                    if link.get('content-type') == 'application/pdf':
                        citation.pdf_url = link.get('URL')
                        citation.pdf_source = 'crossref'
                        break

        elif source == APISource.OPENALEX:
            # OpenAlex-specific field mappings
            if citation.title is None:
                citation.title = metadata_dict.get('display_name') or metadata_dict.get(
                    'title'
                )

            if citation.abstract is None and 'abstract_inverted_index' in metadata_dict:
                # Reconstruct abstract from inverted index
                citation.abstract = self._reconstruct_abstract(
                    metadata_dict['abstract_inverted_index']
                )

            if citation.authors is None and 'authorships' in metadata_dict:
                authors = []
                for authorship in metadata_dict['authorships']:
                    if authorship.get('author') and authorship['author'].get(
                        'display_name'
                    ):
                        authors.append(authorship['author']['display_name'])
                citation.authors = authors if authors else None

            if citation.year is None:
                citation.year = metadata_dict.get('publication_year')

            if citation.journal is None and 'primary_location' in metadata_dict:
                location = metadata_dict['primary_location']
                if location and location.get('source'):
                    citation.journal = location['source'].get('display_name')

            if citation.citation_count is None:
                citation.citation_count = metadata_dict.get('cited_by_count')

            if citation.fields_of_study is None and 'topics' in metadata_dict:
                fields = [
                    topic['display_name']
                    for topic in metadata_dict['topics']
                    if topic.get('display_name')
                ]
                citation.fields_of_study = fields if fields else None

            # Open access info
            if citation.is_open_access is None and 'open_access' in metadata_dict:
                citation.is_open_access = metadata_dict['open_access'].get(
                    'is_oa', False
                )

            if citation.pdf_url is None and 'open_access' in metadata_dict:
                oa_url = metadata_dict['open_access'].get('oa_url')
                if oa_url:
                    citation.pdf_url = oa_url
                    citation.pdf_source = 'openalex'

            # OpenAlex ID as backup
            if citation.backup_id is None and 'id' in metadata_dict:
                openalex_id = metadata_dict['id'].split('/')[-1]
                citation.backup_id = f'openalex:{openalex_id}'

        elif source == APISource.SEMANTIC_SCHOLAR:
            # Semantic Scholar-specific field mappings
            if citation.title is None:
                citation.title = metadata_dict.get('title')

            if citation.abstract is None:
                citation.abstract = metadata_dict.get('abstract')

            if citation.authors is None and 'authors' in metadata_dict:
                authors = [
                    author['name']
                    for author in metadata_dict['authors']
                    if author.get('name')
                ]
                citation.authors = authors if authors else None

            if citation.year is None:
                citation.year = metadata_dict.get('year')

            if citation.venue is None:
                citation.venue = metadata_dict.get('venue')

            if citation.journal is None and 'journal' in metadata_dict:
                journal_data = metadata_dict['journal']
                if journal_data and 'name' in journal_data:
                    citation.journal = journal_data['name']

            if citation.citation_count is None:
                citation.citation_count = metadata_dict.get('citationCount')

            if citation.reference_count is None:
                citation.reference_count = metadata_dict.get('referenceCount')

            if citation.influential_citation_count is None:
                citation.influential_citation_count = metadata_dict.get(
                    'influentialCitationCount'
                )

            if citation.fields_of_study is None:
                citation.fields_of_study = metadata_dict.get('fieldsOfStudy')

            if (
                citation.s2_fields_of_study is None
                and 's2FieldsOfStudy' in metadata_dict
            ):
                s2_fields = metadata_dict['s2FieldsOfStudy']
                if s2_fields and isinstance(s2_fields[0], dict):
                    citation.s2_fields_of_study = [
                        field['category']
                        for field in s2_fields
                        if field.get('category')
                    ]
                else:
                    citation.s2_fields_of_study = s2_fields

            if citation.is_open_access is None:
                citation.is_open_access = metadata_dict.get('isOpenAccess')

            if citation.pdf_url is None and 'openAccessPdf' in metadata_dict:
                oa_pdf = metadata_dict['openAccessPdf']
                if oa_pdf and oa_pdf.get('url'):
                    citation.pdf_url = oa_pdf['url']
                    citation.pdf_source = 's2'

            if citation.url is None:
                citation.url = metadata_dict.get('url')

            # External IDs
            if 'externalIds' in metadata_dict:
                ext_ids = metadata_dict['externalIds']
                if citation.doi is None and 'DOI' in ext_ids:
                    citation.doi = ext_ids['DOI']
                if citation.arxiv_id is None and 'ArXiv' in ext_ids:
                    citation.arxiv_id = ext_ids['ArXiv']

        return citation

    def _reconstruct_abstract(self, inverted_index: Dict[str, List[int]]) -> str:  # noqa: UP006
        """
        Reconstruct abstract from OpenAlex inverted index format.

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

    async def enrich_from_doi(self, citation: Citation, doi: str) -> Citation:
        """
        Enrich citation using DOI via Crossref API.

        Args:
            citation: Citation to enrich
            doi: DOI identifier

        Returns:
            Enriched Citation
        """
        logger.debug(f'Enriching citation from DOI: {doi}')

        metadata = await self._fetch_crossref_metadata(doi)
        if metadata:
            citation = self._merge_metadata(citation, metadata, APISource.CROSSREF)
            self._stats['crossref_enrichments'] += 1
            logger.info(f'Successfully enriched citation from Crossref DOI: {doi}')
        else:
            logger.warning(f'Failed to fetch Crossref metadata for DOI: {doi}')

        return citation

    async def enrich_from_openalex(
        self, citation: Citation, openalex_id: str
    ) -> Citation:
        """
        Enrich citation using OpenAlex ID.

        Args:
            citation: Citation to enrich
            openalex_id: OpenAlex identifier

        Returns:
            Enriched Citation
        """
        logger.debug(f'Enriching citation from OpenAlex ID: {openalex_id}')

        metadata = await self._fetch_openalex_metadata(openalex_id)
        if metadata:
            citation = self._merge_metadata(citation, metadata, APISource.OPENALEX)
            self._stats['openalex_enrichments'] += 1
            logger.info(f'Successfully enriched citation from OpenAlex: {openalex_id}')
        else:
            logger.warning(f'Failed to fetch OpenAlex metadata for ID: {openalex_id}')

        return citation

    async def enrich_from_semantic_scholar(
        self, citation: Citation, s2_paper_id: str
    ) -> Citation:
        """
        Enrich citation using Semantic Scholar paper ID.

        Args:
            citation: Citation to enrich
            s2_paper_id: Semantic Scholar paper ID

        Returns:
            Enriched Citation
        """
        logger.debug(f'Enriching citation from Semantic Scholar ID: {s2_paper_id}')

        metadata = await self._fetch_s2_metadata(s2_paper_id)
        if metadata:
            citation = self._merge_metadata(
                citation, metadata, APISource.SEMANTIC_SCHOLAR
            )
            self._stats['s2_enrichments'] += 1
            logger.info(
                f'Successfully enriched citation from Semantic Scholar: {s2_paper_id}'
            )
        else:
            logger.warning(f'Failed to fetch S2 metadata for ID: {s2_paper_id}')

        return citation

    async def batch_enrich(self, results: List[ResolutionResult]) -> List[Citation]:  # noqa: UP006
        """
        Batch enrich citations from resolution results.

        This method takes resolution results and enriches them using the best
        available data source. It prioritizes:
        1. Crossref for DOI-based enrichment (most reliable)
        2. OpenAlex for abstracts and open access info
        3. Semantic Scholar for citation counts and field classification

        Args:
            results: List of resolution results

        Returns:
            List of fully enriched Citation objects
        """
        logger.info(f'Batch enriching {len(results)} citations from resolution results')

        enriched_citations: List[Citation] = []  # noqa: UP006

        # Limit concurrent enrichment requests to prevent API rate limit exhaustion
        # and resource contention (50 concurrent enrichments max)
        semaphore = asyncio.Semaphore(50)

        async def enrich_with_limit(result):
            """Enrich a single citation with concurrency control."""
            async with semaphore:
                # Create base Citation from matched_data
                if result.matched_data:
                    citation = Citation(**result.matched_data)
                else:
                    # Create minimal citation from original citation text
                    citation = Citation(text=result.citation)

                # Determine enrichment strategy based on available identifiers
                if result.source == APISource.CROSSREF and result.matched_data.get(
                    'doi'
                ):
                    # DOI available - use Crossref as primary source
                    return await self._enrich_citation_prioritized(citation, result)
                elif result.source == APISource.OPENALEX and result.matched_data.get(
                    'openalex_id'
                ):
                    # OpenAlex ID available
                    openalex_id = result.matched_data['openalex_id']
                    return await self.enrich_from_openalex(citation, openalex_id)
                elif (
                    result.source == APISource.SEMANTIC_SCHOLAR
                    and result.matched_data.get('s2_id')
                ):
                    # Semantic Scholar ID available
                    s2_id = result.matched_data['s2_id']
                    return await self.enrich_from_semantic_scholar(citation, s2_id)
                else:
                    # No good identifier - return as-is
                    return citation

        tasks = [enrich_with_limit(result) for result in results]

        # Execute enrichments in parallel with bounded concurrency
        enriched_citations = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_citations = []
        for i, citation in enumerate(enriched_citations):
            if isinstance(citation, Exception):
                logger.error(f'Error enriching citation {i}: {citation}')
                # Use original matched_data if available
                if results[i].matched_data:
                    valid_citations.append(Citation(**results[i].matched_data))
            else:
                valid_citations.append(citation)
                self._stats['total_enriched'] += 1

        logger.info(
            f'Batch enrichment complete: {self._stats["total_enriched"]} citations enriched. '
            f'Sources: Crossref={self._stats["crossref_enrichments"]}, '
            f'OpenAlex={self._stats["openalex_enrichments"]}, '
            f'S2={self._stats["s2_enrichments"]}, '
            f'Errors={self._stats["errors"]}'
        )

        return valid_citations

    async def _enrich_citation_prioritized(
        self, citation: Citation, result: ResolutionResult
    ) -> Citation:
        """
        Enrich citation with fallback priority: Crossref -> OpenAlex -> S2.

        Args:
            citation: Citation to enrich
            result: Resolution result with identifiers

        Returns:
            Enriched Citation
        """
        # Try Crossref first (best for DOI-based metadata)
        if result.matched_data.get('doi'):
            citation = await self.enrich_from_doi(citation, result.matched_data['doi'])

        # If still missing abstract, try OpenAlex
        if citation.abstract is None and result.matched_data.get('openalex_id'):
            citation = await self.enrich_from_openalex(
                citation, result.matched_data['openalex_id']
            )

        # If still missing fields, try Semantic Scholar
        if (
            citation.abstract is None or citation.citation_count is None
        ) and result.matched_data.get('s2_id'):
            citation = await self.enrich_from_semantic_scholar(
                citation, result.matched_data['s2_id']
            )

        return citation

    def get_statistics(self) -> Dict[str, Any]:  # noqa: UP006
        """Get enrichment statistics."""
        return self._stats.copy()
