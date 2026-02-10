"""
Adaptive query routing for RAG systems.

Classifies queries and routes them to appropriate retrieval strategies:
- Direct answer: Simple queries the LLM can answer without retrieval
- Standard RAG: Single retrieval + generation
- Multi-hop RAG: Complex queries requiring multiple retrievals
- CRAG fallback: Low-confidence results trigger corrective retrieval
"""

import asyncio
from enum import Enum
from typing import Any

from langchain_core.documents import Document
from loguru import logger


class QueryType(Enum):
    """Query classification types."""

    DIRECT_ANSWER = 'direct_answer'  # Skip retrieval
    STANDARD_RAG = 'standard_rag'  # Single retrieval
    MULTI_HOP_RAG = 'multi_hop_rag'  # Multiple retrievals
    UNKNOWN = 'unknown'  # Fallback


class QueryRouter:
    """
    Routes queries to appropriate RAG strategies.

    Uses simple heuristics for classification. Can be enhanced with
    semantic-router library for ML-based classification.
    """

    def __init__(
        self,
        enabled: bool = False,
        confidence_threshold: float = 0.6,
        use_semantic_router: bool = False,
    ):
        """
        Initialize query router.

        Args:
            enabled: Whether routing is enabled
            confidence_threshold: Threshold for CRAG fallback (0-1)
            use_semantic_router: Use semantic-router library (requires installation)
        """
        self.enabled = enabled
        self.confidence_threshold = confidence_threshold
        self.use_semantic_router = use_semantic_router

        # Try to initialize semantic-router if requested
        if use_semantic_router:
            try:
                from semantic_router import Route, RouteLayer
                from semantic_router.encoders import HuggingFaceEncoder

                # Define routes with example utterances
                direct_routes = [
                    'What is the capital of France?',
                    'Define machine learning',
                    'Who invented the telephone?',
                    'What does API stand for?',
                ]

                standard_routes = [
                    'Summarize the methodology in this paper',
                    'What are the key findings?',
                    'Explain the experimental setup',
                    'What datasets were used?',
                ]

                multi_hop_routes = [
                    'Compare and contrast approaches A and B',
                    'How does this relate to previous work?',
                    'What are the implications for field X and Y?',
                    'Synthesize findings across multiple papers',
                ]

                # Create routes
                routes = [
                    Route(
                        name='direct_answer',
                        utterances=direct_routes,
                    ),
                    Route(
                        name='standard_rag',
                        utterances=standard_routes,
                    ),
                    Route(
                        name='multi_hop_rag',
                        utterances=multi_hop_routes,
                    ),
                ]

                # Initialize encoder and route layer
                encoder = HuggingFaceEncoder()
                self.route_layer = RouteLayer(encoder=encoder, routes=routes)

                logger.info('Initialized QueryRouter with semantic-router')
            except ImportError:
                logger.warning(
                    'semantic-router not installed, using heuristic classification'
                )
                self.route_layer = None
        else:
            self.route_layer = None

        logger.info(
            f'Initialized QueryRouter (enabled={enabled}, '
            f'semantic={use_semantic_router})'
        )

    def classify_query(self, query: str) -> QueryType:
        """
        Classify query type.

        Args:
            query: User query

        Returns:
            QueryType classification
        """
        if not self.enabled:
            return QueryType.STANDARD_RAG

        # Use semantic-router if available
        if self.route_layer is not None:
            try:
                result = self.route_layer(query)
                if result and result.name:
                    return QueryType(result.name)
            except Exception as e:
                logger.warning(f'Semantic routing failed: {e}, using heuristics')

        # Fallback to heuristic classification
        return self._classify_heuristic(query)

    def _classify_heuristic(self, query: str) -> QueryType:
        """
        Classify query using simple heuristics.

        Args:
            query: User query

        Returns:
            QueryType classification
        """
        query_lower = query.lower()

        # Direct answer keywords (general knowledge)
        direct_keywords = ['what is', 'who is', 'define', 'meaning of']
        if any(kw in query_lower for kw in direct_keywords):
            # But check if it's asking about specific papers/research
            research_keywords = ['paper', 'study', 'research', 'experiment', 'dataset']
            if not any(kw in query_lower for kw in research_keywords):
                return QueryType.DIRECT_ANSWER

        # Multi-hop keywords (complex analysis)
        multi_hop_keywords = [
            'compare',
            'contrast',
            'relate',
            'synthesize',
            'implications',
            'across',
            'between',
            'versus',
            'vs',
        ]
        if any(kw in query_lower for kw in multi_hop_keywords):
            return QueryType.MULTI_HOP_RAG

        # Default to standard RAG
        return QueryType.STANDARD_RAG

    def should_use_crag_fallback(
        self,
        retrieved_docs: list[Document],
        query: str,  # noqa: ARG002
    ) -> bool:
        """
        Determine if CRAG fallback should be triggered.

        Checks if retrieved documents have low relevance scores,
        indicating corrective retrieval is needed.

        Args:
            retrieved_docs: Retrieved documents
            query: Original query

        Returns:
            True if CRAG fallback should be used
        """
        if not self.enabled or not retrieved_docs:
            return False

        # Check average similarity/rerank scores
        scores = []
        for doc in retrieved_docs:
            # Try rerank score first, fall back to similarity
            score = doc.metadata.get('rerank_score') or doc.metadata.get(
                'similarity', 0.0
            )
            scores.append(score)

        if not scores:
            return False

        avg_score = sum(scores) / len(scores)

        # Trigger CRAG if average score is below threshold
        if avg_score < self.confidence_threshold:
            logger.info(
                f'Low confidence (avg={avg_score:.3f} < {self.confidence_threshold}), '
                'triggering CRAG fallback'
            )
            return True

        return False

    async def decompose_query_async(self, query: str, llm_client: Any) -> list[str]:
        """
        Decompose complex query into sub-queries for multi-hop RAG.

        Args:
            query: Complex query to decompose
            llm_client: LLM client for decomposition

        Returns:
            List of sub-queries
        """
        prompt = f"""Decompose this complex research question into 2-4 simpler sub-questions that can be answered independently.

Each sub-question should focus on a specific aspect of the original question.

Original Question: {query}

Sub-Questions (one per line):"""

        try:
            response = await asyncio.to_thread(llm_client.invoke, prompt)

            # Parse sub-questions (one per line)
            sub_queries = [
                line.strip()
                for line in response.content.strip().split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]

            # Remove numbering if present (1., 2., etc.)
            import re

            sub_queries = [re.sub(r'^\d+[\.)]\s*', '', q) for q in sub_queries]

            logger.debug(f'Decomposed query into {len(sub_queries)} sub-queries')
            return sub_queries[:4]  # Limit to 4 sub-queries

        except Exception as e:
            logger.error(f'Query decomposition failed: {e}')
            # Fallback: treat original as single query
            return [query]

    def decompose_query(self, query: str, llm_client: Any) -> list[str]:
        """
        Decompose query (sync wrapper).

        Args:
            query: Complex query
            llm_client: LLM client

        Returns:
            List of sub-queries
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                'decompose_query() called from async context. '
                'Use await decompose_query_async() instead.'
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                return asyncio.run(self.decompose_query_async(query, llm_client))
            else:
                raise
