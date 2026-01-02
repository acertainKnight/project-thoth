import asyncio
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List  # noqa: UP035

from loguru import logger

from thoth.analyze.citations.enrichment_service import CitationEnrichmentService
from thoth.analyze.citations.opencitation import OpenCitationsAPI
from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.resolution_types import (
    CitationResolutionStatus,
    ResolutionResult,
)
from thoth.analyze.citations.scholarly import ScholarlyAPI
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.discovery.api_sources import ArxivClient
from thoth.utilities.schemas import Citation


class CitationEnhancer:
    """Enhances citation data using external APIs."""

    def __init__(self, config):
        self.config = config
        self.use_semanticscholar = config.citation_config.apis.use_semantic_scholar
        self.use_opencitations = config.citation_config.apis.use_opencitations
        self.use_scholarly = config.citation_config.apis.use_scholarly
        self.use_arxiv = config.citation_config.apis.use_arxiv

        # New resolution system configuration
        self.use_resolution_chain = getattr(
            config.citation_config, 'use_resolution_chain', False
        )

        # Initialize Semantic Scholar with performance optimizations
        if self.use_semanticscholar:
            performance_config = getattr(config, 'performance_config', None)
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
                api_key=config.api_keys.semanticscholar_api_key, **ss_kwargs
            )
        else:
            self.semanticscholar_tool = None
        self.opencitations_tool = (
            OpenCitationsAPI(access_token=config.api_keys.opencitations_key)
            if self.use_opencitations and config.api_keys.opencitations_key
            else None
        )
        self.scholarly_tool = ScholarlyAPI() if self.use_scholarly else None
        self.arxiv_tool = ArxivClient() if self.use_arxiv else None

        # Initialize new resolution system components (lazy initialization)
        self._resolution_chain = None
        self._enrichment_service = None

    def enhance(self, citations: list[Citation]) -> list[Citation]:
        """
        Enhances a list of citations by fetching additional data from external APIs.
        """
        # Issue deprecation warning for standard citation enhancement
        warnings.warn(
            'Using CitationEnhancer (standard synchronous enhancement). '
            'For better performance, consider using AsyncCitationEnhancer '
            'which provides async I/O, intelligent caching, and concurrent API calls. '
            'Available through OptimizedDocumentPipeline or async processing workflows.',
            DeprecationWarning,
            stacklevel=2,
        )

        if not citations:
            return []

        # Process with Semantic Scholar first
        if self.use_semanticscholar and self.semanticscholar_tool:
            citations = self.semanticscholar_tool.semantic_scholar_lookup(citations)

        # Process with other services for remaining gaps
        for citation in citations:
            has_identifier, has_missing_fields = self._check_citation(citation)
            if not has_missing_fields:
                continue

            if self.use_opencitations and self.opencitations_tool and has_identifier:
                results = self.opencitations_tool.lookup_metadata_sync(
                    [f'doi:{citation.doi}' if citation.doi else citation.backup_id]
                )
                if results:
                    citation.update_from_opencitation(results[0])

            if (
                self.use_arxiv
                and self.arxiv_tool
                and (not has_identifier or self._check_citation(citation)[1])
            ):
                self._arxiv_lookup([citation])

            if (
                self.use_scholarly
                and self.scholarly_tool
                and (not has_identifier or self._check_citation(citation)[1])
            ):
                self._scholarly_lookup([citation])

        return citations

    def enhance_parallel(self, citations: list[Citation]) -> list[Citation]:
        """
        Enhanced parallel processing of citations using existing APIs.

        This method optimizes the citation enhancement by:
        1. Checking if new resolution chain should be used
        2. Using Semantic Scholar's batch processing first (legacy path)
        3. Grouping remaining citations by API needs
        4. Processing API calls in parallel using ThreadPoolExecutor
        """
        if not citations:
            return []

        # Check if we should use new resolution chain
        if self.use_resolution_chain:
            logger.info('Using new resolution chain for parallel enhancement')  # noqa: F823
            # enhance_with_resolution_chain is now async, so we need to run it
            return asyncio.run(self.enhance_with_resolution_chain(citations))

        # Legacy path: Use Semantic Scholar's existing batch processing first
        if self.use_semanticscholar and self.semanticscholar_tool:
            citations = self.semanticscholar_tool.semantic_scholar_lookup(citations)

        # Step 2: Group citations that still need enhancement
        need_opencitations = []
        need_arxiv = []
        need_scholarly = []

        for citation in citations:
            has_identifier, has_missing_fields = self._check_citation(citation)
            if has_missing_fields:
                if (
                    self.use_opencitations
                    and self.opencitations_tool
                    and has_identifier
                ):
                    need_opencitations.append(citation)
                if (
                    self.use_arxiv
                    and self.arxiv_tool
                    and (not has_identifier or has_missing_fields)
                ):
                    need_arxiv.append(citation)
                if (
                    self.use_scholarly
                    and self.scholarly_tool
                    and (not has_identifier or has_missing_fields)
                ):
                    need_scholarly.append(citation)

        # Step 3: Process remaining APIs in parallel
        perf_config = getattr(self.config, 'performance_config', None)
        if perf_config and hasattr(perf_config, 'workers'):
            worker_config = perf_config.workers.citation_enhancement
            # Resolve "auto" to actual worker count
            if worker_config == 'auto':
                import os

                max_workers = max(1, os.cpu_count() or 3)
            else:
                max_workers = int(worker_config)
        else:
            max_workers = 3  # Fallback default
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            if need_opencitations:
                futures.append(
                    executor.submit(
                        self._process_opencitations_batch, need_opencitations
                    )
                )
            if need_arxiv:
                futures.append(executor.submit(self._process_arxiv_batch, need_arxiv))
            if need_scholarly:
                futures.append(
                    executor.submit(self._process_scholarly_batch, need_scholarly)
                )

            # Wait for all parallel processing to complete
            for future in as_completed(futures):
                try:
                    future.result()  # This will raise any exceptions that occurred
                except Exception as e:
                    from loguru import logger

                    logger.error(f'Error in parallel citation processing: {e}')

        return citations

    def _process_opencitations_batch(self, citations: list[Citation]) -> None:
        """Process multiple citations with OpenCitations in batch."""
        if not citations:
            return

        # Group citations by DOI for batch processing
        dois = []
        citation_map = {}

        for citation in citations:
            if citation.doi:
                doi_key = f'doi:{citation.doi}'
                dois.append(doi_key)
                citation_map[doi_key] = citation
            elif citation.backup_id:
                dois.append(citation.backup_id)
                citation_map[citation.backup_id] = citation

        if dois:
            try:
                # OpenCitations can handle multiple IDs in one request
                results = self.opencitations_tool.lookup_metadata_sync(dois)
                for i, result in enumerate(results):
                    if result and i < len(dois):
                        citation_key = dois[i]
                        if citation_key in citation_map:
                            citation_map[citation_key].update_from_opencitation(result)
            except Exception as e:
                from loguru import logger

                logger.warning(f'Batch OpenCitations lookup failed: {e}')
                # Fallback to individual processing
                for citation in citations:
                    try:
                        doi_key = (
                            f'doi:{citation.doi}'
                            if citation.doi
                            else citation.backup_id
                        )
                        if doi_key:
                            results = self.opencitations_tool.lookup_metadata_sync(
                                [doi_key]
                            )
                            if results:
                                citation.update_from_opencitation(results[0])
                    except Exception:
                        continue

    def _process_arxiv_batch(self, citations: list[Citation]) -> None:
        """Process multiple citations with arXiv."""
        if not citations:
            return

        try:
            # Process all citations at once using existing method
            self._arxiv_lookup(citations)
        except Exception as e:
            from loguru import logger

            logger.warning(f'Batch arXiv lookup failed: {e}')
            # Fallback to individual processing
            for citation in citations:
                try:
                    self._arxiv_lookup([citation])
                except Exception:
                    continue

    def _process_scholarly_batch(self, citations: list[Citation]) -> None:
        """Process multiple citations with Scholarly (Google Scholar)."""
        if not citations:
            return

        # Scholarly doesn't have true batch processing, but we can still parallelize
        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:  # Conservative to avoid rate limits
            futures = [
                executor.submit(self._scholarly_lookup, [citation])
                for citation in citations
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    from loguru import logger

                    logger.debug(f'Individual scholarly lookup failed: {e}')

    def _check_citation(self, citation: Citation) -> tuple[bool, bool]:
        """Checks if a citation has an identifier and if it has missing fields."""
        has_identifier = bool(citation.doi or citation.backup_id)
        has_missing_fields = any(
            getattr(citation, field) is None for field in citation.model_fields
        )
        return has_identifier, has_missing_fields

    def _arxiv_lookup(self, citations: list[Citation]):
        if self.arxiv_tool:
            self.arxiv_tool.arxiv_lookup(citations)

    def _scholarly_lookup(self, citations: list[Citation]):
        if self.scholarly_tool:
            self.scholarly_tool.find_doi_sync(citations[0])
            self.scholarly_tool.find_pdf_url_sync(citations[0])

    def _get_resolution_chain(self) -> CitationResolutionChain:
        """
        Get or initialize the resolution chain (lazy initialization).

        Returns:
            CitationResolutionChain instance
        """
        if self._resolution_chain is None:
            from thoth.analyze.citations.arxiv_resolver import ArxivResolver
            from thoth.analyze.citations.crossref_resolver import CrossrefResolver
            from thoth.analyze.citations.openalex_resolver import OpenAlexResolver

            # Initialize resolvers (including ArXiv for preprints)
            crossref_resolver = CrossrefResolver()
            arxiv_resolver = ArxivResolver()
            openalex_resolver = OpenAlexResolver()

            self._resolution_chain = CitationResolutionChain(
                crossref_resolver=crossref_resolver,
                arxiv_resolver=arxiv_resolver,
                openalex_resolver=openalex_resolver,
                semanticscholar_resolver=self.semanticscholar_tool,
            )
            logger.info('Initialized CitationResolutionChain with ArXiv support')

        return self._resolution_chain

    def _get_enrichment_service(self) -> CitationEnrichmentService:
        """
        Get or initialize the enrichment service (lazy initialization).

        Returns:
            CitationEnrichmentService instance
        """
        if self._enrichment_service is None:
            # Extract API keys from config
            crossref_api_key = getattr(self.config.api_keys, 'crossref_api_key', None)
            openalex_email = getattr(self.config.api_keys, 'openalex_email', None)
            s2_api_key = getattr(self.config.api_keys, 'semanticscholar_api_key', None)

            self._enrichment_service = CitationEnrichmentService(
                crossref_api_key=crossref_api_key,
                openalex_email=openalex_email,
                s2_api_key=s2_api_key,
            )
            logger.info('Initialized CitationEnrichmentService')

        return self._enrichment_service

    async def enhance_with_resolution_chain(
        self,
        citations: List[Citation],  # noqa: UP006
    ) -> List[Citation]:  # noqa: UP006
        """
        Enhance citations using the new resolution chain and enrichment service.

        This method provides improved citation resolution by:
        1. Using CitationResolutionChain to resolve DOIs first
        2. Using CitationEnrichmentService to fetch full metadata
        3. Maintaining backward compatibility with existing enhance() methods
        4. Logging resolution statistics

        Args:
            citations: List of citations to enhance

        Returns:
            List of enhanced citations with resolved metadata
        """
        if not citations:
            return []

        logger.info(
            f'Starting enhanced citation resolution for {len(citations)} citations '
            f'using new resolution chain'
        )

        # Get resolution chain and enrichment service
        resolution_chain = self._get_resolution_chain()
        enrichment_service = self._get_enrichment_service()

        try:
            # Step 1: Resolve DOIs using resolution chain
            logger.info('Step 1: Resolving citations through resolution chain...')
            resolution_results = await resolution_chain.batch_resolve(
                citations, parallel=True
            )

            # Log resolution statistics
            stats = resolution_chain.get_statistics()
            logger.info(
                f'Resolution chain statistics:\n'
                f'  Total processed: {stats["total_processed"]}\n'
                f'  Already has DOI: {stats["already_has_doi"]}\n'
                f'  Resolved via Crossref: {stats["resolved_crossref"]}\n'
                f'  Resolved via OpenAlex: {stats["resolved_openalex"]}\n'
                f'  Resolved via Semantic Scholar: {stats["resolved_semanticscholar"]}\n'
                f'  Unresolved: {stats["unresolved"]}\n'
                f'  High confidence: {stats["high_confidence"]}\n'
                f'  Medium confidence: {stats["medium_confidence"]}\n'
                f'  Low confidence: {stats["low_confidence"]}'
            )

            # Step 2: Apply resolved data back to citations
            logger.info('Step 2: Applying resolved data to citations...')
            enhanced_citations = self._apply_resolution_results(  # noqa: F841
                citations, resolution_results
            )

            # Step 3: Enrich with full metadata using enrichment service
            logger.info('Step 3: Enriching citations with full metadata...')
            enriched_citations = await enrichment_service.batch_enrich(
                resolution_results
            )

            # Log enrichment statistics
            enrich_stats = enrichment_service.get_statistics()
            logger.info(
                f'Enrichment service statistics:\n'
                f'  Total enriched: {enrich_stats["total_enriched"]}\n'
                f'  Crossref enrichments: {enrich_stats["crossref_enrichments"]}\n'
                f'  OpenAlex enrichments: {enrich_stats["openalex_enrichments"]}\n'
                f'  Semantic Scholar enrichments: {enrich_stats["s2_enrichments"]}\n'
                f'  Errors: {enrich_stats["errors"]}\n'
                f'  Retries: {enrich_stats["retries"]}'
            )

            # Close async resources
            await resolution_chain.close()
            await enrichment_service.close()

            logger.info(
                f'Enhanced citation resolution complete: {len(enriched_citations)} '
                f'citations processed'
            )

            return enriched_citations

        except Exception as e:
            logger.error(f'Error in enhanced citation resolution: {e}', exc_info=True)
            # Fallback to original citations
            return citations

    def _apply_resolution_results(
        self,
        citations: List[Citation],  # noqa: UP006
        results: List[ResolutionResult],  # noqa: UP006
    ) -> List[Citation]:  # noqa: UP006
        """
        Apply resolution results back to original citations.

        Args:
            citations: Original citations
            results: Resolution results from resolution chain

        Returns:
            Citations with resolved data applied
        """
        for citation, result in zip(citations, results):  # noqa: B905
            if (
                result.status
                in (CitationResolutionStatus.RESOLVED, CitationResolutionStatus.PARTIAL)
                and result.matched_data
            ):
                # Update citation with resolved data (only non-None fields)
                if result.matched_data.get('doi') and not citation.doi:
                    citation.doi = result.matched_data['doi']

                if result.matched_data.get('title') and not citation.title:
                    citation.title = result.matched_data['title']

                if result.matched_data.get('authors') and not citation.authors:
                    citation.authors = result.matched_data['authors']

                if result.matched_data.get('year') and not citation.year:
                    citation.year = result.matched_data['year']

                if result.matched_data.get('journal') and not citation.journal:
                    citation.journal = result.matched_data['journal']

                if result.matched_data.get('volume') and not citation.volume:
                    citation.volume = result.matched_data['volume']

                if result.matched_data.get('issue') and not citation.issue:
                    citation.issue = result.matched_data['issue']

                if result.matched_data.get('pages') and not citation.pages:
                    citation.pages = result.matched_data['pages']

                if result.matched_data.get('url') and not citation.url:
                    citation.url = result.matched_data['url']

                if result.matched_data.get('abstract') and not citation.abstract:
                    citation.abstract = result.matched_data['abstract']

                if (
                    result.matched_data.get('citation_count')
                    and not citation.citation_count
                ):
                    citation.citation_count = result.matched_data['citation_count']

                logger.debug(
                    f'Applied resolution result to citation: '
                    f'status={result.status}, confidence={result.confidence_score:.2f}, '
                    f'source={result.source}'
                )

        return citations
