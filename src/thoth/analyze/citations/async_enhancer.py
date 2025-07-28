"""
Async citation enhancer for improved I/O performance with external APIs.

This module provides async versions of citation enhancement operations
for better performance when dealing with multiple external API calls.
"""

import asyncio
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import aiohttp
from loguru import logger

from thoth.analyze.citations.opencitation import OpenCitationsAPI
from thoth.analyze.citations.scholarly import ScholarlyAPI
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.discovery.api_sources import ArxivClient
from thoth.utilities.schemas import Citation


class AsyncCitationEnhancer:
    """
    Async citation enhancer for improved performance with external APIs.

    This enhancer provides:
    - Async HTTP requests for better I/O performance
    - Intelligent rate limiting and retry logic
    - Caching to avoid duplicate API calls
    - Parallel processing with controlled concurrency
    """

    def __init__(self, config, session: aiohttp.ClientSession | None = None):
        self.config = config
        self.use_semanticscholar = config.citation_config.use_semanticscholar
        self.use_opencitations = config.citation_config.use_opencitations
        self.use_scholarly = config.citation_config.use_scholarly
        self.use_arxiv = config.citation_config.use_arxiv

        # HTTP session for async requests
        self._session = session

        # Simple in-memory cache for API responses
        self._api_cache = {}
        self._cache_ttl = 3600  # 1 hour TTL

        # Rate limiting
        self._rate_limiters = {
            'semantic_scholar': asyncio.Semaphore(10),  # 10 concurrent requests
            'opencitations': asyncio.Semaphore(5),  # 5 concurrent requests
            'arxiv': asyncio.Semaphore(3),  # 3 concurrent requests
            'scholarly': asyncio.Semaphore(2),  # 2 concurrent requests
        }

        # Initialize sync tools for fallback
        self._init_sync_tools()

    def _init_sync_tools(self):
        """Initialize synchronous tools for fallback operations."""
        # Initialize Semantic Scholar with performance optimizations
        if self.use_semanticscholar:
            performance_config = getattr(self.config, 'performance_config', None)
            ss_kwargs = {}
            if performance_config:
                ss_kwargs.update(
                    {
                        'max_retries': performance_config.semanticscholar_max_retries,
                        'max_backoff_seconds': performance_config.semanticscholar_max_backoff_seconds,
                        'backoff_multiplier': performance_config.semanticscholar_backoff_multiplier,
                    }
                )
            self.semanticscholar_tool = SemanticScholarAPI(
                api_key=self.config.api_keys.semanticscholar_api_key, **ss_kwargs
            )
        else:
            self.semanticscholar_tool = None

        self.opencitations_tool = (
            OpenCitationsAPI(access_token=self.config.api_keys.opencitations_key)
            if self.use_opencitations and self.config.api_keys.opencitations_key
            else None
        )
        self.scholarly_tool = ScholarlyAPI() if self.use_scholarly else None
        self.arxiv_tool = ArxivClient() if self.use_arxiv else None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def cleanup(self):
        """Clean up resources."""
        if self._session:
            await self._session.close()

    def _get_cache_key(self, api_name: str, identifier: str) -> str:
        """Generate cache key for API responses."""
        return hashlib.md5(f'{api_name}:{identifier}'.encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: dict) -> bool:
        """Check if cache entry is still valid."""
        return time.time() - cache_entry['timestamp'] < self._cache_ttl

    async def enhance_async(self, citations: list[Citation]) -> list[Citation]:
        """
        Enhance citations asynchronously with improved I/O performance.

        Args:
            citations: List of citations to enhance

        Returns:
            List of enhanced citations
        """
        if not citations:
            return []

        logger.info(f'Starting async enhancement of {len(citations)} citations')

        # Step 1: Use Semantic Scholar batch processing (still fastest approach)
        if self.use_semanticscholar and self.semanticscholar_tool:
            # Run in thread pool to avoid blocking async loop
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                citations = await loop.run_in_executor(
                    executor,
                    self.semanticscholar_tool.semantic_scholar_lookup,
                    citations,
                )
            logger.info('Completed Semantic Scholar batch processing')

        # Step 2: Identify citations needing additional enhancement
        enhancement_tasks = self._create_enhancement_tasks(citations)

        if not enhancement_tasks:
            logger.info('No additional enhancement needed')
            return citations

        # Step 3: Process enhancement tasks asynchronously
        logger.info(f'Processing {len(enhancement_tasks)} enhancement tasks')
        await asyncio.gather(*enhancement_tasks, return_exceptions=True)

        logger.info('Async citation enhancement completed')
        return citations

    def _create_enhancement_tasks(self, citations: list[Citation]) -> list:
        """Create async enhancement tasks for citations."""
        tasks = []

        for citation in citations:
            has_identifier, has_missing_fields = self._check_citation(citation)

            if not has_missing_fields:
                continue

            # OpenCitations enhancement
            if (
                self.use_opencitations
                and self.opencitations_tool
                and has_identifier
                and citation.doi
            ):
                tasks.append(self._enhance_with_opencitations(citation))

            # ArXiv enhancement
            if (
                self.use_arxiv
                and self.arxiv_tool
                and (citation.arxiv_id or not has_identifier)
            ):
                tasks.append(self._enhance_with_arxiv(citation))

            # Scholarly enhancement (limited use due to rate limits)
            if (
                self.use_scholarly
                and self.scholarly_tool
                and not has_identifier
                and has_missing_fields
            ):
                tasks.append(self._enhance_with_scholarly(citation))

        return tasks

    async def _enhance_with_opencitations(self, citation: Citation):
        """Enhance citation using OpenCitations API asynchronously."""
        if not citation.doi:
            return

        cache_key = self._get_cache_key('opencitations', citation.doi)

        # Check cache first
        if cache_key in self._api_cache and self._is_cache_valid(
            self._api_cache[cache_key]
        ):
            cached_data = self._api_cache[cache_key]['data']
            if cached_data:
                citation.update_from_opencitation(cached_data)
            return

        async with self._rate_limiters['opencitations']:
            try:
                await asyncio.sleep(0.1)  # Basic rate limiting

                # Use sync tool in thread pool for now
                # TODO: Replace with native async implementation
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    results = await loop.run_in_executor(
                        executor,
                        self.opencitations_tool.lookup_metadata_sync,
                        [f'doi:{citation.doi}'],
                    )

                if results:
                    citation.update_from_opencitation(results[0])
                    # Cache the result
                    self._api_cache[cache_key] = {
                        'data': results[0],
                        'timestamp': time.time(),
                    }
                    logger.debug(
                        f'Enhanced citation via OpenCitations: {citation.title[:50]}'
                    )
                else:
                    # Cache negative result
                    self._api_cache[cache_key] = {
                        'data': None,
                        'timestamp': time.time(),
                    }

            except Exception as e:
                logger.warning(
                    f'OpenCitations enhancement failed for {citation.title[:50]}: {e}'
                )

    async def _enhance_with_arxiv(self, citation: Citation):
        """Enhance citation using arXiv API asynchronously."""
        if not citation.arxiv_id and not citation.title:
            return

        identifier = citation.arxiv_id or citation.title
        cache_key = self._get_cache_key('arxiv', identifier)

        # Check cache first
        if cache_key in self._api_cache and self._is_cache_valid(
            self._api_cache[cache_key]
        ):
            cached_data = self._api_cache[cache_key]['data']
            if cached_data:
                self._update_citation_from_arxiv(citation, cached_data)
            return

        async with self._rate_limiters['arxiv']:
            try:
                await asyncio.sleep(0.2)  # ArXiv rate limiting

                # Use sync tool in thread pool
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    if citation.arxiv_id:
                        results = await loop.run_in_executor(
                            executor, self.arxiv_tool.search_by_id, citation.arxiv_id
                        )
                    else:
                        results = await loop.run_in_executor(
                            executor, self.arxiv_tool.search_by_title, citation.title
                        )

                if results:
                    self._update_citation_from_arxiv(citation, results[0])
                    # Cache the result
                    self._api_cache[cache_key] = {
                        'data': results[0],
                        'timestamp': time.time(),
                    }
                    logger.debug(f'Enhanced citation via arXiv: {citation.title[:50]}')
                else:
                    # Cache negative result
                    self._api_cache[cache_key] = {
                        'data': None,
                        'timestamp': time.time(),
                    }

            except Exception as e:
                logger.warning(
                    f'ArXiv enhancement failed for {citation.title[:50]}: {e}'
                )

    async def _enhance_with_scholarly(self, citation: Citation):
        """Enhance citation using Scholarly API asynchronously."""
        if not citation.title:
            return

        cache_key = self._get_cache_key('scholarly', citation.title)

        # Check cache first
        if cache_key in self._api_cache and self._is_cache_valid(
            self._api_cache[cache_key]
        ):
            cached_data = self._api_cache[cache_key]['data']
            if cached_data:
                self._update_citation_from_scholarly(citation, cached_data)
            return

        async with self._rate_limiters['scholarly']:
            try:
                await asyncio.sleep(1.0)  # Conservative rate limiting for Scholarly

                # Use sync tool in thread pool
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    results = await loop.run_in_executor(
                        executor, self.scholarly_tool.search_by_title, citation.title
                    )

                if results:
                    self._update_citation_from_scholarly(citation, results[0])
                    # Cache the result
                    self._api_cache[cache_key] = {
                        'data': results[0],
                        'timestamp': time.time(),
                    }
                    logger.debug(
                        f'Enhanced citation via Scholarly: {citation.title[:50]}'
                    )
                else:
                    # Cache negative result
                    self._api_cache[cache_key] = {
                        'data': None,
                        'timestamp': time.time(),
                    }

            except Exception as e:
                logger.warning(
                    f'Scholarly enhancement failed for {citation.title[:50]}: {e}'
                )

    def _update_citation_from_arxiv(self, citation: Citation, arxiv_data: dict):
        """Update citation with arXiv data."""
        if 'id' in arxiv_data:
            citation.arxiv_id = arxiv_data['id']
        if 'title' in arxiv_data and not citation.title:
            citation.title = arxiv_data['title']
        if 'authors' in arxiv_data and not citation.authors:
            citation.authors = arxiv_data['authors']
        if 'published' in arxiv_data and not citation.year:
            try:
                citation.year = int(arxiv_data['published'][:4])
            except (ValueError, TypeError):
                pass
        if 'pdf_url' in arxiv_data and not citation.pdf_url:
            citation.pdf_url = arxiv_data['pdf_url']

    def _update_citation_from_scholarly(self, citation: Citation, scholarly_data: dict):
        """Update citation with Scholarly data."""
        if 'title' in scholarly_data and not citation.title:
            citation.title = scholarly_data['title']
        if 'authors' in scholarly_data and not citation.authors:
            citation.authors = scholarly_data['authors']
        if 'year' in scholarly_data and not citation.year:
            citation.year = scholarly_data['year']
        if 'venue' in scholarly_data and not citation.venue:
            citation.venue = scholarly_data['venue']
        if 'url' in scholarly_data and not citation.url:
            citation.url = scholarly_data['url']

    def _check_citation(self, citation: Citation) -> tuple[bool, bool]:
        """
        Check citation completeness.

        Returns:
            tuple[bool, bool]: (has_identifier, has_missing_fields)
        """
        has_identifier = bool(citation.doi or citation.arxiv_id or citation.url)

        # Check for missing important fields
        missing_fields = []
        if not citation.authors:
            missing_fields.append('authors')
        if not citation.year:
            missing_fields.append('year')
        if not citation.venue and not citation.journal:
            missing_fields.append('venue/journal')
        if not citation.pdf_url and not citation.url:
            missing_fields.append('url')

        has_missing_fields = len(missing_fields) > 0

        return has_identifier, has_missing_fields

    async def batch_enhance_async(
        self, citation_batches: list[list[Citation]]
    ) -> list[list[Citation]]:
        """
        Enhance multiple batches of citations asynchronously.

        This method provides optimal performance for large-scale citation processing
        by processing multiple batches concurrently while respecting rate limits.
        """
        logger.info(f'Starting batch enhancement of {len(citation_batches)} batches')

        # Process batches with controlled concurrency
        max_concurrent_batches = 3  # Avoid overwhelming APIs

        results = []
        for i in range(0, len(citation_batches), max_concurrent_batches):
            batch_group = citation_batches[i : i + max_concurrent_batches]

            tasks = [self.enhance_async(batch) for batch in batch_group]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f'Batch enhancement failed: {result}')
                    results.append([])  # Empty result for failed batch
                else:
                    results.append(result)

            # Small delay between batch groups to be respectful to APIs
            if i + max_concurrent_batches < len(citation_batches):
                await asyncio.sleep(0.5)

        logger.info(f'Completed batch enhancement: {len(results)} batches processed')
        return results

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        valid_entries = sum(
            1 for entry in self._api_cache.values() if self._is_cache_valid(entry)
        )

        return {
            'total_entries': len(self._api_cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self._api_cache) - valid_entries,
            'cache_ttl_seconds': self._cache_ttl,
        }

    def clear_cache(self):
        """Clear the API response cache."""
        self._api_cache.clear()
        logger.info('Citation enhancement cache cleared')
