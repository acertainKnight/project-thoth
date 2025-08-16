"""
Memory Pipeline Hooks - Uses modular components.

This module imports all components from their modular structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

# Import all components from their modules
from thoth.memory.enrichment import MemoryEnricher
from thoth.memory.filtering import MemoryFilter
from thoth.memory.scoring import SalienceScorer

if TYPE_CHECKING:
    from letta import Agent


class MemoryWritePipeline:
    """
    Complete pipeline for processing memories before storage.
    
    Combines filtering, enrichment, and scoring into a single pipeline.
    """

    def __init__(self):
        """Initialize the write pipeline with all components."""
        self.filter = MemoryFilter()
        self.enricher = MemoryEnricher()
        self.scorer = SalienceScorer()

    async def process(
        self,
        agent: 'Agent',
        content: str,
        role: str = 'user',
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Process a memory through the complete pipeline.

        Args:
            agent: Letta agent instance
            content: Memory content
            role: Message role (user, assistant, system)
            metadata: Additional metadata
            user_context: User context information

        Returns:
            tuple[bool, dict[str, Any]]: (should_store, processed_metadata)
        """
        try:
            # Step 1: Filter
            should_store, filter_reason = self.filter.should_store(
                content, role, metadata
            )
            
            if not should_store:
                logger.debug(f'Memory filtered out: {filter_reason}')
                return False, {'filter_reason': filter_reason}

            # Step 2: Enrich
            enriched_metadata = self.enricher.enrich(
                content, role, metadata, user_context
            )

            # Step 3: Score
            salience_score = self.scorer.calculate_salience(
                content, role, enriched_metadata, user_context
            )
            
            enriched_metadata['salience_score'] = salience_score
            enriched_metadata['filter_reason'] = filter_reason

            # Log high-salience memories
            if salience_score > 0.7:
                logger.info(
                    f'High salience memory detected (score: {salience_score:.2f}): '
                    f'{content[:50]}...'
                )

            return True, enriched_metadata

        except Exception as e:
            logger.error(f'Error in memory write pipeline: {e}')
            # Return safe defaults on error
            return True, metadata or {}


class MemoryReadPipeline:
    """
    Pipeline for processing memories during retrieval.
    
    Can filter and rank retrieved memories based on context.
    """

    def __init__(self):
        """Initialize the read pipeline."""
        self.scorer = SalienceScorer()

    def process(
        self,
        memories: list[dict[str, Any]],
        query_context: dict[str, Any] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Process retrieved memories.

        Args:
            memories: List of retrieved memories
            query_context: Context about the current query
            max_results: Maximum number of results to return

        Returns:
            list[dict[str, Any]]: Processed and ranked memories
        """
        try:
            # Re-score based on query context if provided
            if query_context:
                for memory in memories:
                    # Adjust salience based on query relevance
                    original_score = memory.get('metadata', {}).get(
                        'salience_score', 0.5
                    )
                    
                    # Simple keyword matching for query relevance
                    query_keywords = set(
                        query_context.get('query', '').lower().split()
                    )
                    memory_content = memory.get('content', '').lower()
                    
                    keyword_matches = sum(
                        1 for keyword in query_keywords if keyword in memory_content
                    )
                    
                    # Boost score based on keyword matches
                    query_boost = min(keyword_matches * 0.1, 0.3)
                    adjusted_score = min(original_score + query_boost, 1.0)
                    
                    if 'metadata' not in memory:
                        memory['metadata'] = {}
                    memory['metadata']['adjusted_salience_score'] = adjusted_score
                    memory['metadata']['query_relevance'] = keyword_matches

            # Sort by adjusted score (or original if no adjustment)
            memories.sort(
                key=lambda m: m.get('metadata', {}).get(
                    'adjusted_salience_score',
                    m.get('metadata', {}).get('salience_score', 0)
                ),
                reverse=True
            )

            # Limit results if requested
            if max_results:
                memories = memories[:max_results]

            return memories

        except Exception as e:
            logger.error(f'Error in memory read pipeline: {e}')
            # Return original memories on error
            return memories


# Convenience functions for direct usage
def create_write_pipeline() -> MemoryWritePipeline:
    """Create a new memory write pipeline instance."""
    return MemoryWritePipeline()


def create_read_pipeline() -> MemoryReadPipeline:
    """Create a new memory read pipeline instance."""
    return MemoryReadPipeline()


# Export all components and pipelines
__all__ = [
    'MemoryFilter',
    'MemoryEnricher', 
    'SalienceScorer',
    'MemoryWritePipeline',
    'MemoryReadPipeline',
    'create_write_pipeline',
    'create_read_pipeline',
]
