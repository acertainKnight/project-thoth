"""
Memory processing pipelines using modular components.

This module provides high-level pipelines that orchestrate the memory
processing components for writing and retrieving memories.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .components import (
    MemoryEnricher,
    MemoryFilter,
    RelevanceScorer,
    RetrievalMetrics,
    RetrievalRanker,
    SalienceScorer,
)


class MemoryWritePipeline:
    """
    Complete pipeline for processing memories before storage.

    Combines salience scoring, filtering, and metadata enrichment.
    """

    def __init__(
        self,
        min_salience: float = 0.1,
        enable_enrichment: bool = True,
        enable_filtering: bool = True,
    ):
        """
        Initialize the memory write pipeline.

        Args:
            min_salience: Minimum salience threshold for storage
            enable_enrichment: Whether to enrich metadata
            enable_filtering: Whether to apply content filtering
        """
        self.salience_scorer = SalienceScorer()
        self.memory_filter = MemoryFilter(min_salience=min_salience)
        self.memory_enricher = MemoryEnricher() if enable_enrichment else None

        self.enable_enrichment = enable_enrichment
        self.enable_filtering = enable_filtering

        logger.info(
            f'Memory write pipeline initialized (filtering: {enable_filtering}, enrichment: {enable_enrichment})'
        )

    def process_memory(
        self,
        content: str,
        role: str,
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Process a single memory through the complete pipeline.

        Args:
            content: Memory content
            role: Message role
            metadata: Existing metadata
            user_context: User context for processing

        Returns:
            Processed memory dict or None if filtered out
        """
        try:
            # Calculate salience score
            salience_score = self.salience_scorer.calculate_salience(
                content=content,
                role=role,
                metadata=metadata,
                user_context=user_context,
            )

            # Apply filtering if enabled
            if self.enable_filtering:
                should_store = self.memory_filter.should_store_memory(
                    content=content,
                    role=role,
                    salience_score=salience_score,
                    metadata=metadata,
                )

                if not should_store:
                    logger.debug('Memory filtered out during processing')
                    return None

            # Create base memory object
            processed_memory = {
                'content': content,
                'role': role,
                'salience_score': salience_score,
                'metadata': metadata or {},
            }

            # Enrich metadata if enabled
            if self.enable_enrichment and self.memory_enricher:
                enriched_metadata = self.memory_enricher.enrich_metadata(
                    content=content,
                    role=role,
                    existing_metadata=metadata,
                    user_context=user_context,
                )
                processed_memory['metadata'] = enriched_metadata

            logger.debug(
                f'Memory processed successfully (salience: {salience_score:.3f})'
            )
            return processed_memory

        except Exception as e:
            logger.error(f'Error processing memory: {e}')
            return None

    def process_memory_batch(
        self,
        memories: list[dict[str, Any]],
        user_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Process a batch of memories through the pipeline.

        Args:
            memories: List of memory dictionaries with 'content', 'role', and 'metadata'
            user_context: User context for processing

        Returns:
            List of processed memories that passed filtering
        """
        processed_memories = []

        for memory in memories:
            content = memory.get('content', '')
            role = memory.get('role', 'unknown')
            metadata = memory.get('metadata')

            processed = self.process_memory(
                content=content,
                role=role,
                metadata=metadata,
                user_context=user_context,
            )

            if processed is not None:
                processed_memories.append(processed)

        logger.info(
            f'Processed {len(memories)} memories, {len(processed_memories)} passed filtering'
        )
        return processed_memories

    def update_config(
        self,
        min_salience: float | None = None,
        enable_enrichment: bool | None = None,
        enable_filtering: bool | None = None,
    ) -> None:
        """
        Update pipeline configuration.

        Args:
            min_salience: New minimum salience threshold
            enable_enrichment: Whether to enable enrichment
            enable_filtering: Whether to enable filtering
        """
        if min_salience is not None:
            self.memory_filter.set_min_salience(min_salience)

        if enable_enrichment is not None:
            self.enable_enrichment = enable_enrichment
            if enable_enrichment and not self.memory_enricher:
                self.memory_enricher = MemoryEnricher()
            elif not enable_enrichment:
                self.memory_enricher = None

        if enable_filtering is not None:
            self.enable_filtering = enable_filtering

        logger.info('Memory write pipeline configuration updated')

    def get_stats(self, memories: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Get processing statistics for a set of memories.

        Args:
            memories: Memories to analyze

        Returns:
            dict: Processing statistics
        """
        if self.enable_filtering:
            filter_stats = self.memory_filter.get_filter_stats(memories)
        else:
            filter_stats = {
                'total_memories': len(memories),
                'would_store': len(memories),
            }

        # Calculate salience distribution
        salience_scores = []
        for memory in memories:
            content = memory.get('content', '')
            role = memory.get('role', 'unknown')
            metadata = memory.get('metadata')

            score = self.salience_scorer.calculate_salience(
                content=content, role=role, metadata=metadata
            )
            salience_scores.append(score)

        if salience_scores:
            stats = {
                **filter_stats,
                'salience_stats': {
                    'mean': sum(salience_scores) / len(salience_scores),
                    'min': min(salience_scores),
                    'max': max(salience_scores),
                    'high_salience_count': len(
                        [s for s in salience_scores if s >= 0.8]
                    ),
                },
                'pipeline_config': {
                    'filtering_enabled': self.enable_filtering,
                    'enrichment_enabled': self.enable_enrichment,
                    'min_salience_threshold': self.memory_filter.min_salience,
                },
            }
        else:
            stats = filter_stats

        return stats


class MemoryRetrievalPipeline:
    """
    Complete pipeline for retrieving and ranking memories.

    Combines relevance scoring, ranking, and performance tracking.
    """

    def __init__(
        self,
        relevance_weight: float = 0.4,
        salience_weight: float = 0.3,
        recency_weight: float = 0.2,
        diversity_weight: float = 0.1,
        enable_metrics: bool = True,
    ):
        """
        Initialize the memory retrieval pipeline.

        Args:
            relevance_weight: Weight for relevance in ranking
            salience_weight: Weight for salience in ranking
            recency_weight: Weight for recency in ranking
            diversity_weight: Weight for diversity in ranking
            enable_metrics: Whether to track performance metrics
        """
        self.relevance_scorer = RelevanceScorer()
        self.retrieval_ranker = RetrievalRanker(
            relevance_weight=relevance_weight,
            salience_weight=salience_weight,
            recency_weight=recency_weight,
            diversity_weight=diversity_weight,
        )
        self.metrics = RetrievalMetrics() if enable_metrics else None

        self.enable_metrics = enable_metrics

        logger.info('Memory retrieval pipeline initialized')

    def retrieve_memories(
        self,
        memories: list[dict[str, Any]],
        query: str,
        max_results: int = 10,
        user_preferences: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve and rank memories for a query.

        Args:
            memories: Pool of memories to search
            query: Search query
            max_results: Maximum number of results
            user_preferences: User preferences for ranking
            user_id: User identifier for metrics
            session_id: Session identifier for metrics

        Returns:
            List of ranked, relevant memories
        """
        import time

        start_time = time.time()

        try:
            if not memories:
                return []

            # Score memories for relevance
            scored_memories = self.relevance_scorer.score_memory_set(
                memories=memories,
                query=query,
                context={'timestamp': time.time()},
            )

            # Convert to memory list with relevance scores
            memories_with_scores = []
            for memory, relevance_score in scored_memories:
                memory = memory.copy()  # Don't modify original
                memory['_relevance_score'] = relevance_score
                memories_with_scores.append(memory)

            # Rank memories using composite scoring
            ranked_memories = self.retrieval_ranker.rank_memories(
                memories=memories_with_scores,
                query=query,
                user_preferences=user_preferences,
                max_results=max_results,
            )

            # Record metrics if enabled
            if self.enable_metrics and self.metrics:
                response_time_ms = (time.time() - start_time) * 1000
                self.metrics.record_query(
                    query=query,
                    results_count=len(ranked_memories),
                    response_time_ms=response_time_ms,
                    user_id=user_id,
                    session_id=session_id,
                )

            logger.debug(
                f'Retrieved {len(ranked_memories)} memories for query: "{query}"'
            )
            return ranked_memories

        except Exception as e:
            logger.error(f'Memory retrieval failed: {e}')
            return []

    def record_feedback(
        self,
        query: str,
        result_rank: int,
        feedback_type: str,
        user_id: str | None = None,
    ) -> None:
        """
        Record user feedback on retrieval results.

        Args:
            query: Original query
            result_rank: Rank of result that received feedback
            feedback_type: Type of feedback
            user_id: User identifier
        """
        if self.enable_metrics and self.metrics:
            self.metrics.record_user_feedback(
                query=query,
                result_rank=result_rank,
                feedback_type=feedback_type,
                user_id=user_id,
            )

    def get_performance_stats(self) -> dict[str, Any]:
        """Get retrieval performance statistics."""
        if self.enable_metrics and self.metrics:
            return self.metrics.get_performance_summary()
        else:
            return {}

    def update_ranking_weights(
        self,
        relevance_weight: float | None = None,
        salience_weight: float | None = None,
        recency_weight: float | None = None,
        diversity_weight: float | None = None,
    ) -> None:
        """
        Update ranking weights based on performance feedback.

        Args:
            relevance_weight: New relevance weight
            salience_weight: New salience weight
            recency_weight: New recency weight
            diversity_weight: New diversity weight
        """
        self.retrieval_ranker.update_weights(
            relevance_weight=relevance_weight,
            salience_weight=salience_weight,
            recency_weight=recency_weight,
            diversity_weight=diversity_weight,
        )

    def clear_old_metrics(self, days_to_keep: int = 7) -> None:
        """Clear old performance metrics."""
        if self.enable_metrics and self.metrics:
            self.metrics.clear_old_metrics(days_to_keep=days_to_keep)
