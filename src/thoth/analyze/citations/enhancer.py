import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

from thoth.analyze.citations.opencitation import OpenCitationsAPI
from thoth.analyze.citations.scholarly import ScholarlyAPI
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.discovery.sources import ArxivClient
from thoth.utilities.schemas import Citation


class CitationEnhancer:
    """Enhances citation data using external APIs."""

    def __init__(self, config):
        self.config = config
        self.use_semanticscholar = config.citation_config.use_semanticscholar
        self.use_opencitations = config.citation_config.use_opencitations
        self.use_scholarly = config.citation_config.use_scholarly
        self.use_arxiv = config.citation_config.use_arxiv

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
        1. Using Semantic Scholar's batch processing first
        2. Grouping remaining citations by API needs
        3. Processing API calls in parallel using ThreadPoolExecutor
        """
        if not citations:
            return []

        # Step 1: Use Semantic Scholar's existing batch processing first
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
        max_workers = getattr(self.config, 'performance_config', None)
        if max_workers:
            max_workers = max_workers.citation_enhancement_workers
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
