"""
Citation Resolution Chain Coordinator

This module implements the citation resolution chain that orchestrates resolution
across multiple API sources with intelligent fallback logic and confidence-based
early stopping.

Resolution Flow:
---------------
1. Check if citation already has DOI → Skip resolution
2. Check if citation has ArXiv ID → Try Semantic Scholar first (best for arXiv)
3. Try Crossref → Stop if high confidence match found
4. Try OpenAlex → Stop if high confidence match found
5. Try Semantic Scholar → Accept even without DOI (metadata-only match)
6. Return UNRESOLVED if no good matches found

Features:
---------
- Concurrent batch processing with asyncio
- Intelligent source selection based on available identifiers
- Confidence-based early stopping to reduce API calls
- Comprehensive logging of resolution decisions
- Progress tracking for large batches
"""

import asyncio  # noqa: I001
import time
from typing import Any, Dict, List  # noqa: UP035

from loguru import logger

from thoth.analyze.citations.arxiv_resolver import (
    ArxivResolver,
    ArxivMatch,
)
from thoth.analyze.citations.crossref_resolver import (
    CrossrefResolver,
    MatchCandidate as CrossrefMatch,
)
from thoth.analyze.citations.openalex_resolver import (
    OpenAlexResolver,
    MatchCandidate as OpenAlexMatch,
)
from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ConfidenceLevel,
    MatchCandidate,
    ResolutionMetadata,
    ResolutionResult,
)
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.utilities.schemas.citations import Citation


# Confidence thresholds for early stopping (per improved citation resolution spec)
HIGH_CONFIDENCE_THRESHOLD = 0.85  # Accept automatically (spec requirement)
MEDIUM_CONFIDENCE_THRESHOLD = 0.70  # Accept if clear winner (spec requirement)
TITLE_THRESHOLD = 0.80  # Minimum title similarity (spec: validation checklist)


class CitationResolutionChain:
    """
    Citation resolution chain coordinator.

    Orchestrates citation resolution across multiple API sources with intelligent
    fallback logic, early stopping based on confidence scores, and batch processing.

    Attributes:
        crossref_resolver: CrossRef API resolver for DOI lookup
        openalex_resolver: OpenAlex API resolver for fuzzy matching
        semanticscholar_resolver: Semantic Scholar API for ML-enhanced matching
    """

    def __init__(
        self,
        crossref_resolver: CrossrefResolver | None = None,
        arxiv_resolver: ArxivResolver | None = None,
        openalex_resolver: OpenAlexResolver | None = None,
        semanticscholar_resolver: SemanticScholarAPI | None = None,
    ):
        """
        Initialize resolution chain with API resolvers.

        Args:
            crossref_resolver: CrossRef API resolver instance
            arxiv_resolver: ArXiv API resolver instance
            openalex_resolver: OpenAlex API resolver instance
            semanticscholar_resolver: Semantic Scholar API instance
        """
        # Initialize resolvers with defaults if not provided
        self.crossref_resolver = crossref_resolver or CrossrefResolver()
        self.arxiv_resolver = arxiv_resolver or ArxivResolver()
        self.openalex_resolver = openalex_resolver or OpenAlexResolver()
        self.semanticscholar_resolver = semanticscholar_resolver or SemanticScholarAPI()

        # Resolution statistics
        self._stats = {
            'total_processed': 0,
            'already_has_doi': 0,
            'resolved_crossref': 0,
            'resolved_arxiv': 0,
            'resolved_openalex': 0,
            'resolved_semanticscholar': 0,
            'unresolved': 0,
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
        }

        logger.info('Initialized CitationResolutionChain with all API sources')

    async def resolve(
        self,
        citation: Citation,
        _recursion_depth: int = 0,
        _max_depth: int = 3,
    ) -> ResolutionResult:
        """
        Resolve a single citation through the resolution chain.

        Resolution flow:
        1. Check if citation already has DOI (skip)
        2. Check if citation has ArXiv ID (try Semantic Scholar first)
        3. Try Crossref → stop if high confidence
        4. Try OpenAlex → stop if high confidence
        5. Try Semantic Scholar → accept even without DOI
        6. Return UNRESOLVED if no good matches

        Args:
            citation: Citation to resolve
            _recursion_depth: Internal recursion tracking (default: 0)
            _max_depth: Maximum recursion depth allowed (default: 3)

        Returns:
            ResolutionResult with resolution outcome and metadata
        """
        # Circuit breaker: prevent infinite recursion
        if _recursion_depth >= _max_depth:
            logger.warning(
                f'Maximum recursion depth ({_max_depth}) reached for citation: '
                f'{citation.text or citation.title or "Unknown"}. Returning UNRESOLVED.'
            )
            metadata = ResolutionMetadata()
            metadata.error_message = f'Max recursion depth ({_max_depth}) exceeded'
            return ResolutionResult(
                citation=citation.text or citation.title or 'Unknown citation',
                status=CitationResolutionStatus.UNRESOLVED,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.NONE,
                source=None,
                matched_data=None,
                metadata=metadata,
            )
        start_time = time.time()
        metadata = ResolutionMetadata()
        candidates: List[MatchCandidate] = []  # noqa: UP006

        citation_text = citation.text or citation.title or 'Unknown citation'
        logger.debug(f'Starting resolution chain for: {citation_text[:80]}...')

        # Step 1: Check if citation already has DOI
        if citation.doi:
            logger.info(
                f'Citation already has DOI: {citation.doi} - skipping resolution'
            )
            self._stats['already_has_doi'] += 1
            self._stats['total_processed'] += 1

            # Calculate processing time even when skipping resolution
            processing_time = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds
            metadata.processing_time_ms = processing_time

            return ResolutionResult(
                citation=citation_text,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=1.0,
                confidence_level=ConfidenceLevel.HIGH,
                source=None,
                matched_data={'doi': citation.doi},
                metadata=metadata,
            )

        # Step 2: Check for ArXiv ID - try Semantic Scholar first for arXiv papers
        if citation.arxiv_id or (
            citation.backup_id and citation.backup_id.startswith('arxiv:')
        ):
            logger.debug(
                f'Citation has ArXiv ID, trying Semantic Scholar first: '
                f'{citation.arxiv_id or citation.backup_id}'
            )
            result = await self._try_semantic_scholar(citation, metadata, candidates)
            if result and result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
                logger.info(
                    f'Found high-confidence match via Semantic Scholar (ArXiv): '
                    f'score={result.confidence_score:.2f}'
                )
                result.metadata.processing_time_ms = (time.time() - start_time) * 1000
                self._stats['resolved_semanticscholar'] += 1
                self._stats['high_confidence'] += 1
                self._stats['total_processed'] += 1
                return result

        # Step 3: Try Crossref (best for DOI-based resolution)
        logger.debug('Trying Crossref resolver...')
        try:
            result = await self._try_crossref(citation, metadata, candidates)
            if result and result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
                logger.info(
                    f'Found high-confidence match via Crossref: '
                    f'score={result.confidence_score:.2f}, doi={result.matched_data.get("doi") if result.matched_data else None}'
                )
                result.metadata.processing_time_ms = (time.time() - start_time) * 1000
                self._stats['resolved_crossref'] += 1
                self._stats['high_confidence'] += 1
                self._stats['total_processed'] += 1
                return result
        except Exception as e:
            logger.warning(f'Crossref resolver failed: {e}')
            # Continue to next source

        # Step 4: Try ArXiv (excellent for preprints and ML/AI papers)
        logger.debug('Trying ArXiv resolver...')
        try:
            result = await self._try_arxiv(citation, metadata, candidates)
        except Exception as e:
            logger.warning(f'ArXiv resolver failed: {e}')
            result = None
        if result and result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
            logger.info(
                f'Found high-confidence match via ArXiv: '
                f'score={result.confidence_score:.2f}, arxiv_id={result.matched_data.get("arxiv_id") if result.matched_data else None}'
            )
            result.metadata.processing_time_ms = (time.time() - start_time) * 1000
            self._stats['resolved_arxiv'] += 1
            self._stats['high_confidence'] += 1
            self._stats['total_processed'] += 1
            return result

        # Step 5: Try OpenAlex (better fuzzy matching than Crossref)
        logger.debug('Trying OpenAlex resolver...')
        try:
            result = await self._try_openalex(citation, metadata, candidates)
        except Exception as e:
            logger.warning(f'OpenAlex resolver failed: {e}')
            result = None
        if result and result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
            logger.info(
                f'Found high-confidence match via OpenAlex: '
                f'score={result.confidence_score:.2f}, doi={result.matched_data.get("doi") if result.matched_data else None}'
            )
            result.metadata.processing_time_ms = (time.time() - start_time) * 1000
            self._stats['resolved_openalex'] += 1
            self._stats['high_confidence'] += 1
            self._stats['total_processed'] += 1
            return result

        # Step 6: Try Semantic Scholar (if not already tried for ArXiv)
        if not (
            citation.arxiv_id
            or (citation.backup_id and citation.backup_id.startswith('arxiv:'))
        ):
            logger.debug('Trying Semantic Scholar resolver...')
            result = await self._try_semantic_scholar(citation, metadata, candidates)
            if result and result.confidence_score >= MEDIUM_CONFIDENCE_THRESHOLD:
                logger.info(
                    f'Found medium-confidence match via Semantic Scholar: '
                    f'score={result.confidence_score:.2f}'
                )
                result.metadata.processing_time_ms = (time.time() - start_time) * 1000
                self._stats['resolved_semanticscholar'] += 1
                if result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
                    self._stats['high_confidence'] += 1
                else:
                    self._stats['medium_confidence'] += 1
                self._stats['total_processed'] += 1
                return result

        # Step 7: No good matches found - return UNRESOLVED
        logger.warning(
            f'No suitable matches found for citation: {citation_text[:80]}...'
        )
        processing_time = (time.time() - start_time) * 1000
        metadata.processing_time_ms = processing_time
        self._stats['unresolved'] += 1
        self._stats['low_confidence'] += 1
        self._stats['total_processed'] += 1

        return ResolutionResult(
            citation=citation_text,
            status=CitationResolutionStatus.UNRESOLVED,
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            source=None,
            matched_data=None,
            candidates=candidates,
            metadata=metadata,
        )

    async def _try_crossref(
        self,
        citation: Citation,
        metadata: ResolutionMetadata,
        candidates: List[MatchCandidate],  # noqa: UP006
    ) -> ResolutionResult | None:
        """
        Try resolving citation via Crossref API.

        Args:
            citation: Citation to resolve
            metadata: Resolution metadata to update
            candidates: List to append match candidates to

        Returns:
            ResolutionResult if successful match found, None otherwise
        """
        try:
            metadata.api_sources_tried.append(APISource.CROSSREF)
            matches = await self.crossref_resolver.resolve_citation(citation)

            if not matches:
                logger.debug('No Crossref matches found')
                return None

            # Take best match
            best_match = matches[0]
            confidence = self._calculate_crossref_confidence(best_match, citation)

            # Convert to standard MatchCandidate
            # Normalize Crossref score from 0-100+ range to 0.0-1.0
            # Note: Crossref can return scores > 100 for very strong matches
            normalized_crossref_score = min((best_match.score or 0.0) / 100.0, 1.0)
            candidate = MatchCandidate(
                candidate_data=self._crossref_match_to_dict(best_match),
                raw_score=confidence,
                component_scores={
                    'crossref_score': normalized_crossref_score,
                },
                source=APISource.CROSSREF,
            )
            candidates.append(candidate)

            if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
                status = (
                    CitationResolutionStatus.RESOLVED
                    if confidence >= HIGH_CONFIDENCE_THRESHOLD
                    else CitationResolutionStatus.PARTIAL
                )

                return ResolutionResult(
                    citation=citation.text or citation.title or 'Unknown',
                    status=status,
                    confidence_score=confidence,
                    confidence_level=(
                        ConfidenceLevel.HIGH
                        if confidence >= HIGH_CONFIDENCE_THRESHOLD
                        else ConfidenceLevel.MEDIUM
                    ),
                    source=APISource.CROSSREF,
                    matched_data=self._crossref_match_to_dict(best_match),
                    candidates=candidates.copy(),
                    metadata=metadata,
                )

            return None

        except Exception as e:
            logger.error(f'Error in Crossref resolution: {e}')
            metadata.error_message = f'Crossref error: {str(e)}'  # noqa: RUF010
            return None

    async def _try_arxiv(
        self,
        citation: Citation,
        metadata: ResolutionMetadata,
        candidates: List[MatchCandidate],  # noqa: UP006
    ) -> ResolutionResult | None:
        """
        Try resolving citation via ArXiv API.

        Args:
            citation: Citation to resolve
            metadata: Resolution metadata to update
            candidates: List to append match candidates to

        Returns:
            ResolutionResult if successful match found, None otherwise
        """
        try:
            metadata.api_sources_tried.append(APISource.ARXIV)
            matches = await self.arxiv_resolver.resolve_citation(citation)

            if not matches:
                logger.debug('No ArXiv matches found')
                return None

            # Take best match
            best_match = matches[0]
            confidence = self._calculate_arxiv_confidence(best_match, citation)

            # Convert to standard MatchCandidate
            candidate = MatchCandidate(
                candidate_data=self._arxiv_match_to_dict(best_match),
                raw_score=confidence,
                component_scores={
                    'title_match': 0.9,  # ArXiv title matching is generally reliable
                    'has_doi': 1.0 if best_match.doi else 0.0,
                },
                source=APISource.ARXIV,
            )
            candidates.append(candidate)

            if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
                status = (
                    CitationResolutionStatus.RESOLVED
                    if confidence >= HIGH_CONFIDENCE_THRESHOLD
                    else CitationResolutionStatus.PARTIAL
                )

                return ResolutionResult(
                    citation=citation.text or citation.title or 'Unknown',
                    status=status,
                    confidence_score=confidence,
                    confidence_level=(
                        ConfidenceLevel.HIGH
                        if confidence >= HIGH_CONFIDENCE_THRESHOLD
                        else ConfidenceLevel.MEDIUM
                    ),
                    source=APISource.ARXIV,
                    matched_data=self._arxiv_match_to_dict(best_match),
                    candidates=candidates.copy(),
                    metadata=metadata,
                )

            return None

        except Exception as e:
            logger.error(f'Error in ArXiv resolution: {e}')
            metadata.error_message = f'ArXiv error: {str(e)}'  # noqa: RUF010
            return None

    async def _try_openalex(
        self,
        citation: Citation,
        metadata: ResolutionMetadata,
        candidates: List[MatchCandidate],  # noqa: UP006
    ) -> ResolutionResult | None:
        """
        Try resolving citation via OpenAlex API.

        Args:
            citation: Citation to resolve
            metadata: Resolution metadata to update
            candidates: List to append match candidates to

        Returns:
            ResolutionResult if successful match found, None otherwise
        """
        try:
            metadata.api_sources_tried.append(APISource.OPENALEX)
            matches = await self.openalex_resolver.resolve_citation(citation)

            if not matches:
                logger.debug('No OpenAlex matches found')
                return None

            # Take best match (already sorted by confidence)
            best_match = matches[0]
            confidence = best_match.confidence_score

            # Convert to standard MatchCandidate
            candidate = MatchCandidate(
                candidate_data=self._openalex_match_to_dict(best_match),
                raw_score=confidence,
                component_scores={
                    'openalex_confidence': confidence,
                },
                source=APISource.OPENALEX,
            )
            candidates.append(candidate)

            if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
                status = (
                    CitationResolutionStatus.RESOLVED
                    if confidence >= HIGH_CONFIDENCE_THRESHOLD
                    else CitationResolutionStatus.PARTIAL
                )

                return ResolutionResult(
                    citation=citation.text or citation.title or 'Unknown',
                    status=status,
                    confidence_score=confidence,
                    confidence_level=(
                        ConfidenceLevel.HIGH
                        if confidence >= HIGH_CONFIDENCE_THRESHOLD
                        else ConfidenceLevel.MEDIUM
                    ),
                    source=APISource.OPENALEX,
                    matched_data=self._openalex_match_to_dict(best_match),
                    candidates=candidates.copy(),
                    metadata=metadata,
                )

            return None

        except Exception as e:
            logger.error(f'Error in OpenAlex resolution: {e}')
            metadata.error_message = f'OpenAlex error: {str(e)}'  # noqa: RUF010
            return None

    async def _try_semantic_scholar(
        self,
        citation: Citation,
        metadata: ResolutionMetadata,
        candidates: List[MatchCandidate],  # noqa: UP006
    ) -> ResolutionResult | None:
        """
        Try resolving citation via Semantic Scholar API.

        Note: Semantic Scholar is synchronous, so we wrap it in asyncio.to_thread.

        Args:
            citation: Citation to resolve
            metadata: Resolution metadata to update
            candidates: List to append match candidates to

        Returns:
            ResolutionResult if successful match found, None otherwise
        """
        try:
            metadata.api_sources_tried.append(APISource.SEMANTIC_SCHOLAR)

            # Semantic Scholar API is synchronous, run in thread pool
            def lookup_paper():
                # Try ArXiv lookup first if available
                if citation.arxiv_id:
                    return self.semanticscholar_resolver.paper_lookup_by_arxiv(
                        citation.arxiv_id
                    )
                elif citation.backup_id and citation.backup_id.startswith('arxiv:'):
                    arxiv_id = citation.backup_id.split(':', 1)[1]
                    return self.semanticscholar_resolver.paper_lookup_by_arxiv(arxiv_id)
                elif citation.doi:
                    return self.semanticscholar_resolver.paper_lookup_by_doi(
                        citation.doi
                    )
                elif citation.title:
                    # Title search
                    results = self.semanticscholar_resolver.paper_search(
                        f'"{citation.title}"', limit=1
                    )
                    return results[0] if results else None
                return None

            paper_data = await asyncio.to_thread(lookup_paper)

            if not paper_data:
                logger.debug('No Semantic Scholar matches found')
                return None

            # Calculate confidence score
            confidence = self._calculate_semanticscholar_confidence(
                paper_data, citation
            )

            # Convert to standard MatchCandidate
            candidate = MatchCandidate(
                candidate_data=paper_data,
                raw_score=confidence,
                component_scores={
                    'title_match': 0.9
                    if paper_data.get('title') == citation.title
                    else 0.7,
                    'has_doi': 1.0
                    if paper_data.get('externalIds', {}).get('DOI')
                    else 0.0,
                },
                source=APISource.SEMANTIC_SCHOLAR,
            )
            candidates.append(candidate)

            # Semantic Scholar accepts matches even without DOI if confidence is good
            if confidence >= MEDIUM_CONFIDENCE_THRESHOLD:
                status = (
                    CitationResolutionStatus.RESOLVED
                    if confidence >= HIGH_CONFIDENCE_THRESHOLD
                    else CitationResolutionStatus.PARTIAL
                )

                # Extract DOI if available
                doi = None
                if paper_data.get('externalIds'):
                    doi = paper_data['externalIds'].get('DOI')

                matched_data = {
                    'title': paper_data.get('title'),
                    'doi': doi,
                    'year': paper_data.get('year'),
                    'authors': [
                        a.get('name')
                        for a in paper_data.get('authors', [])
                        if a.get('name')
                    ],
                    'venue': paper_data.get('venue'),
                    'citation_count': paper_data.get('citationCount'),
                    'abstract': paper_data.get('abstract'),
                }

                return ResolutionResult(
                    citation=citation.text or citation.title or 'Unknown',
                    status=status,
                    confidence_score=confidence,
                    confidence_level=(
                        ConfidenceLevel.HIGH
                        if confidence >= HIGH_CONFIDENCE_THRESHOLD
                        else ConfidenceLevel.MEDIUM
                    ),
                    source=APISource.SEMANTIC_SCHOLAR,
                    matched_data=matched_data,
                    candidates=candidates.copy(),
                    metadata=metadata,
                )

            return None

        except Exception as e:
            logger.error(f'Error in Semantic Scholar resolution: {e}')
            metadata.error_message = f'Semantic Scholar error: {str(e)}'  # noqa: RUF010
            return None

    def _calculate_crossref_confidence(
        self, match: CrossrefMatch, citation: Citation
    ) -> float:
        """
        Calculate confidence score for Crossref match with spec-compliant validation.

        Uses weighted scoring per improved citation resolution spec:
        - Title: 45% weight (must be ≥ 0.80)
        - Authors: 25% weight
        - Year: 15% weight (±1 acceptable)
        - Journal: 15% weight

        Args:
            match: Crossref match candidate
            citation: Original citation

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Crossref provides a relevance score (use as baseline)
        crossref_relevance = (match.score or 0.0) / 100.0  # Normalize to 0-1

        # Calculate title similarity (45% weight, spec: must be ≥ 0.80)
        title_sim = 0.0
        if citation.title and match.title:
            title_sim = self._simple_title_similarity(citation.title, match.title)

        # Reject if title similarity below spec threshold
        if title_sim < TITLE_THRESHOLD:
            return 0.0  # Hard reject per spec validation checklist

        # Calculate year score (15% weight, spec: ±1 acceptable)
        year_score = 0.0
        if citation.year and match.year:
            year_diff = abs(citation.year - match.year)
            if year_diff == 0:
                year_score = 1.0
            elif year_diff == 1:
                year_score = 0.8  # Acceptable per spec
            elif year_diff == 2:
                year_score = 0.4  # Tolerable
            # else: 0.0

        # Calculate author overlap (25% weight - basic check)
        author_score = (
            0.5  # Default middle value (Crossref doesn't provide full author matching)
        )
        if citation.authors and match.authors:
            # Simple first author check
            if len(citation.authors) > 0 and len(match.authors) > 0:
                first_input = citation.authors[0].lower()
                first_match = match.authors[0].lower()
                if first_input in first_match or first_match in first_input:
                    author_score = 0.8

        # Weighted combination (spec-compliant)
        final_score = (
            0.45 * title_sim
            + 0.25 * author_score
            + 0.15 * year_score
            + 0.15 * crossref_relevance  # Use Crossref score as journal proxy
        )

        return min(final_score, 1.0)

    def _calculate_semanticscholar_confidence(
        self,
        paper_data: dict[str, Any],
        citation: Citation,
    ) -> float:
        """
        Calculate confidence score for Semantic Scholar match with spec-compliant validation.

        Uses weighted scoring per improved citation resolution spec:
        - Title: 45% weight (must be ≥ 0.80)
        - Authors: 25% weight
        - Year: 15% weight (±1 acceptable)
        - Quality indicators: 15% weight (DOI, citation count)

        Args:
            paper_data: Semantic Scholar paper data
            citation: Original citation

        Returns:
            Confidence score between 0.0 and 1.0
        """  # noqa: W505
        # Calculate title similarity (45% weight, spec: must be ≥ 0.80)
        title_sim = 0.0
        if citation.title and paper_data.get('title'):
            title_sim = self._simple_title_similarity(
                citation.title, paper_data['title']
            )

        # Reject if title similarity below spec threshold
        if title_sim < TITLE_THRESHOLD:
            return 0.0  # Hard reject per spec validation checklist

        # Calculate year score (15% weight, spec: ±1 acceptable)
        year_score = 0.0
        if citation.year and paper_data.get('year'):
            year_diff = abs(citation.year - paper_data['year'])
            if year_diff == 0:
                year_score = 1.0
            elif year_diff == 1:
                year_score = 0.8  # Acceptable per spec
            elif year_diff == 2:
                year_score = 0.4  # Tolerable

        # Calculate author overlap (25% weight - spec: at least one must match)
        author_score = 0.0
        if citation.authors and paper_data.get('authors'):
            s2_authors = [a.get('name', '').lower() for a in paper_data['authors']]
            input_authors = [a.lower() for a in citation.authors]

            # Check for any author overlap
            for input_auth in input_authors:
                for s2_auth in s2_authors:
                    # Check if last names match (simple token overlap)
                    input_tokens = input_auth.split()
                    s2_tokens = s2_auth.split()
                    if any(
                        t1 == t2
                        for t1 in input_tokens
                        for t2 in s2_tokens
                        if len(t1) > 2
                    ):
                        author_score = 0.8  # Found author match
                        break
                if author_score > 0:
                    break

            # If no match found, set low score (but not zero - S2 data might be incomplete)  # noqa: W505
            if author_score == 0.0:
                author_score = 0.3  # Benefit of doubt for S2

        # Quality indicators (15% weight)
        quality_score = 0.0
        # Has DOI (indicator of quality)
        if paper_data.get('externalIds', {}).get('DOI'):
            quality_score += 0.7
        # Has reasonable citation count (indicator it's a real paper)
        citation_count = paper_data.get('citationCount', 0)
        if citation_count > 0:
            quality_score += 0.3

        # Weighted combination (spec-compliant)
        final_score = (
            0.45 * title_sim
            + 0.25 * author_score
            + 0.15 * year_score
            + 0.15 * quality_score
        )

        return min(final_score, 1.0)

    def _simple_title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate simple title similarity score.

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not title1 or not title2:
            return 0.0

        # Normalize titles
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()

        # Exact match
        if t1 == t2:
            return 1.0

        # Token-based similarity (Jaccard)
        tokens1 = set(t1.split())
        tokens2 = set(t2.split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def _crossref_match_to_dict(self, match: CrossrefMatch) -> Dict[str, Any]:  # noqa: UP006
        """Convert Crossref MatchCandidate to dict."""
        return {
            'doi': match.doi,
            'title': match.title,
            'authors': match.authors,
            'journal': match.container_title,
            'year': match.year,
            'volume': match.volume,
            'issue': match.issue,
            'pages': match.pages,
            'url': match.url,
            'abstract': match.abstract,
            'citation_count': match.citation_count,
        }

    def _calculate_arxiv_confidence(
        self, match: ArxivMatch, citation: Citation
    ) -> float:
        """
        Calculate confidence score for ArXiv match.

        Uses weighted scoring similar to other sources:
        - Title: 45% weight (must be ≥ 0.80)
        - Authors: 25% weight
        - Year: 15% weight (±1 acceptable)
        - Quality: 15% weight (has DOI)

        Args:
            match: ArXiv match candidate
            citation: Original citation

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Calculate title similarity (45% weight)
        title_sim = 0.0
        if citation.title and match.title:
            title_sim = self._simple_title_similarity(citation.title, match.title)

        # Reject if title similarity below threshold
        if title_sim < TITLE_THRESHOLD:
            return 0.0

        # Calculate year score (15% weight)
        year_score = 0.0
        if citation.year and match.year:
            year_diff = abs(citation.year - match.year)
            if year_diff == 0:
                year_score = 1.0
            elif year_diff == 1:
                year_score = 0.8
            elif year_diff == 2:
                year_score = 0.4

        # Calculate author overlap (25% weight)
        author_score = 0.5  # Default
        if citation.authors and match.authors:
            if len(citation.authors) > 0 and len(match.authors) > 0:
                first_input = citation.authors[0].lower()
                first_match = match.authors[0].lower()
                if first_input in first_match or first_match in first_input:
                    author_score = 0.8

        # Quality score (15% weight) - has DOI is a good indicator
        quality_score = 1.0 if match.doi else 0.5

        # Weighted combination
        final_score = (
            0.45 * title_sim
            + 0.25 * author_score
            + 0.15 * year_score
            + 0.15 * quality_score
        )

        return min(final_score, 1.0)

    def _arxiv_match_to_dict(self, match: ArxivMatch) -> Dict[str, Any]:  # noqa: UP006
        """Convert ArXiv match to dict."""
        return {
            'arxiv_id': match.arxiv_id,
            'doi': match.doi,
            'title': match.title,
            'authors': match.authors,
            'year': match.year,
            'abstract': match.abstract,
            'pdf_url': match.pdf_url,
            'categories': match.categories,
            'published': match.published,
            'updated': match.updated,
        }

    def _openalex_match_to_dict(self, match: OpenAlexMatch) -> Dict[str, Any]:  # noqa: UP006
        """Convert OpenAlex MatchCandidate to dict."""
        return {
            'doi': match.doi,
            'title': match.title,
            'authors': match.authors,
            'year': match.year,
            'venue': match.venue,
            'abstract': match.abstract,
            'citation_count': match.citation_count,
            'url': match.url,
            'pdf_url': match.pdf_url,
            'is_open_access': match.is_open_access,
            'openalex_id': match.openalex_id,
        }

    async def batch_resolve(
        self,
        citations: list[Citation],
        parallel: bool = True,
    ) -> List[ResolutionResult]:  # noqa: UP006
        """
        Resolve multiple citations in batch.

        Args:
            citations: List of citations to resolve
            parallel: If True, process citations concurrently

        Returns:
            List of ResolutionResult objects
        """
        if not citations:
            return []

        logger.info(
            f'Starting batch resolution for {len(citations)} citations '
            f'(parallel={parallel})'
        )

        start_time = time.time()

        if parallel:
            # Process citations concurrently with bounded parallelism
            # Limit to 50 concurrent tasks to prevent resource exhaustion
            semaphore = asyncio.Semaphore(50)

            async def resolve_with_limit(citation):
                async with semaphore:
                    return await self.resolve(citation)

            tasks = [resolve_with_limit(citation) for citation in citations]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f'Error resolving citation {i}: {result}',
                        exc_info=result,
                    )
                    # Create error result
                    citation = citations[i]
                    citation_text = citation.text or citation.title or 'Unknown'
                    final_results.append(
                        ResolutionResult(
                            citation=citation_text,
                            status=CitationResolutionStatus.FAILED,
                            confidence_score=0.0,
                            confidence_level=ConfidenceLevel.LOW,
                            source=None,
                            matched_data=None,
                            metadata=ResolutionMetadata(error_message=str(result)),
                        )
                    )
                else:
                    final_results.append(result)
        else:
            # Process citations sequentially
            final_results = []
            for i, citation in enumerate(citations):
                logger.debug(f'Processing citation {i + 1}/{len(citations)}')
                result = await self.resolve(citation)
                final_results.append(result)

        elapsed = time.time() - start_time

        # Log summary statistics
        self._log_batch_summary(final_results, elapsed)

        return final_results

    def _log_batch_summary(
        self,
        results: list[ResolutionResult],
        elapsed: float,
    ) -> None:
        """
        Log summary statistics for batch resolution.

        Args:
            results: List of resolution results
            elapsed: Elapsed time in seconds
        """
        total = len(results)
        resolved = sum(
            1
            for r in results
            if r.status
            in (CitationResolutionStatus.RESOLVED, CitationResolutionStatus.PARTIAL)
        )
        unresolved = sum(
            1 for r in results if r.status == CitationResolutionStatus.UNRESOLVED
        )
        failed = sum(1 for r in results if r.status == CitationResolutionStatus.FAILED)

        high_conf = sum(
            1 for r in results if r.confidence_level == ConfidenceLevel.HIGH
        )
        med_conf = sum(
            1 for r in results if r.confidence_level == ConfidenceLevel.MEDIUM
        )
        low_conf = sum(1 for r in results if r.confidence_level == ConfidenceLevel.LOW)

        # Count by source
        crossref = sum(1 for r in results if r.source == APISource.CROSSREF)
        openalex = sum(1 for r in results if r.source == APISource.OPENALEX)
        semantic = sum(1 for r in results if r.source == APISource.SEMANTIC_SCHOLAR)

        logger.info(
            f'Batch resolution complete in {elapsed:.2f}s:\n'
            f'  Total: {total}\n'
            f'  Resolved: {resolved} ({resolved / total * 100:.1f}%)\n'
            f'  Unresolved: {unresolved} ({unresolved / total * 100:.1f}%)\n'
            f'  Failed: {failed} ({failed / total * 100:.1f}%)\n'
            f'  Confidence: HIGH={high_conf}, MEDIUM={med_conf}, LOW={low_conf}\n'
            f'  Sources: Crossref={crossref}, OpenAlex={openalex}, '
            f'SemanticScholar={semantic}\n'
            f'  Avg time: {elapsed / total * 1000:.1f}ms per citation'
        )

    def get_statistics(self) -> Dict[str, Any]:  # noqa: UP006
        """
        Get resolution statistics.

        Returns:
            Dictionary with resolution statistics
        """
        return self._stats.copy()

    async def close(self) -> None:
        """Close all API clients and cleanup resources."""
        logger.info('Closing CitationResolutionChain and API clients')
        await self.crossref_resolver.close()
        # OpenAlex and Semantic Scholar don't have async close methods
        # but we'll close Semantic Scholar's httpx client
        if hasattr(self.semanticscholar_resolver, 'client'):
            self.semanticscholar_resolver.client.close()
        logger.info('CitationResolutionChain closed successfully')
