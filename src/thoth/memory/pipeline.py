"""
Memory Pipeline Hooks - Compatibility wrapper.

This module now imports from the modular structure for better organization.
All functionality is preserved through imports.
"""

# Import all components from their new locations
from thoth.memory.scoring import SalienceScorer

# For now, keep other classes here until fully modularized
# This preserves backward compatibility while we migrate

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger


class MemoryFilter:
    """
    Filter memories before storage based on quality and relevance criteria.

    This helps prevent storage of low-quality or redundant memories.
    """

    def __init__(self):
        """Initialize the memory filter with filtering criteria."""
        # Minimum content length to consider meaningful
        self.min_content_length = 10

        # Maximum content length to prevent excessive storage
        self.max_content_length = 10000

        # Patterns that indicate low-quality content
        self.noise_patterns = [
            r'^(ok|okay|sure|yes|no|thanks|thank you)[\.\!]?$',  # Single word responses
            r'^\.{3,}$',  # Just ellipsis
            r'^\s*$',  # Empty or whitespace only
            r'^(test|testing|hello|hi)[\.\!]?$',  # Test messages
        ]

        # Duplicate detection window (seconds)
        self.duplicate_window = 60  # 1 minute

        # Recent messages cache for duplicate detection
        self.recent_messages: list[tuple[str, datetime]] = []

    def should_store(
        self, content: str, role: str, metadata: dict[str, Any] | None = None
    ) -> tuple[bool, str]:
        """
        Determine if a memory should be stored.

        Args:
            content: Memory content
            role: Message role
            metadata: Additional metadata

        Returns:
            tuple[bool, str]: (should_store, reason)
        """
        try:
            # Length checks
            if len(content) < self.min_content_length:
                return False, 'Content too short'

            if len(content) > self.max_content_length:
                return False, 'Content too long'

            # Noise pattern checks
            content_lower = content.lower().strip()
            for pattern in self.noise_patterns:
                if re.match(pattern, content_lower):
                    return False, f'Matches noise pattern: {pattern}'

            # System messages are often repetitive
            if role == 'system' and not self._is_important_system_message(content):
                return False, 'Non-critical system message'

            # Check for duplicates in recent window
            if self._is_duplicate(content):
                return False, 'Duplicate of recent message'

            # Error messages without context
            if metadata and metadata.get('error'):
                error_msg = str(metadata.get('error', '')).lower()
                if any(
                    trivial in error_msg
                    for trivial in ['connection', 'timeout', 'retry']
                ):
                    return False, 'Trivial error message'

            # All checks passed
            return True, 'Passed all filters'

        except Exception as e:
            logger.error(f'Error in memory filter: {e}')
            # Default to storing on error
            return True, 'Filter error - defaulting to store'

    def _is_important_system_message(self, content: str) -> bool:
        """Check if a system message contains important information."""
        important_keywords = [
            'initialized',
            'loaded',
            'connected',
            'error',
            'warning',
            'failed',
            'research',
            'agent',
            'model',
        ]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in important_keywords)

    def _is_duplicate(self, content: str) -> bool:
        """Check if content is duplicate of recent message."""
        current_time = datetime.now()

        # Clean old entries from cache
        self.recent_messages = [
            (msg, time)
            for msg, time in self.recent_messages
            if (current_time - time).total_seconds() < self.duplicate_window
        ]

        # Check for duplicate
        content_normalized = content.strip().lower()
        for recent_msg, _ in self.recent_messages:
            if recent_msg.strip().lower() == content_normalized:
                return True

        # Add to cache
        self.recent_messages.append((content, current_time))
        return False


class MemoryEnricher:
    """
    Enrich memories with additional context and metadata before storage.

    This enhances the value and searchability of stored memories.
    """

    def __init__(self):
        """Initialize the memory enricher."""
        # Patterns for extracting structured information
        self.url_pattern = re.compile(r'https?://[^\s]+')
        self.doi_pattern = re.compile(r'10\.\d+/[\w\-\._]+')
        self.arxiv_pattern = re.compile(r'arXiv:(\d+\.\d+)')
        self.email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

        # Code block detection
        self.code_pattern = re.compile(r'```[\s\S]*?```|`[^`]+`')

        # Question detection
        self.question_pattern = re.compile(
            r'(what|how|why|when|where|which|who|can|could|would|should|is|are|do|does)\s+.*\?',
            re.IGNORECASE,
        )

    def enrich(
        self, content: str, role: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Enrich memory with extracted features and metadata.

        Args:
            content: Memory content
            role: Message role
            metadata: Existing metadata

        Returns:
            dict[str, Any]: Enriched metadata
        """
        try:
            enriched = metadata.copy() if metadata else {}

            # Extract URLs
            urls = self.url_pattern.findall(content)
            if urls:
                enriched['urls'] = urls
                enriched['has_urls'] = True

            # Extract DOIs
            dois = self.doi_pattern.findall(content)
            if dois:
                enriched['dois'] = dois
                enriched['has_academic_refs'] = True

            # Extract arXiv IDs
            arxiv_ids = self.arxiv_pattern.findall(content)
            if arxiv_ids:
                enriched['arxiv_ids'] = arxiv_ids
                enriched['has_academic_refs'] = True

            # Detect code blocks
            code_blocks = self.code_pattern.findall(content)
            if code_blocks:
                enriched['has_code'] = True
                enriched['code_block_count'] = len(code_blocks)

            # Detect questions
            if self.question_pattern.search(content):
                enriched['is_question'] = True

            # Add temporal context
            enriched['timestamp'] = datetime.now().isoformat()
            enriched['day_of_week'] = datetime.now().strftime('%A')
            enriched['hour_of_day'] = datetime.now().hour

            # Content statistics
            enriched['content_length'] = len(content)
            enriched['word_count'] = len(content.split())
            enriched['line_count'] = len(content.splitlines())

            # Role-specific enrichment
            if role == 'user':
                enriched['user_message'] = True
                # Detect command-like patterns
                if content.strip().startswith(('/', '!', '.')):
                    enriched['is_command'] = True

            elif role == 'assistant':
                enriched['assistant_message'] = True
                # Detect if response contains citations
                if '[' in content and ']' in content:
                    enriched['may_have_citations'] = True

            # Topic detection (simple keyword-based)
            topics = self._detect_topics(content)
            if topics:
                enriched['topics'] = topics

            logger.debug(f'Enriched memory with {len(enriched)} metadata fields')
            return enriched

        except Exception as e:
            logger.error(f'Error enriching memory: {e}')
            return metadata or {}

    def _detect_topics(self, content: str) -> list[str]:
        """Simple topic detection based on keywords."""
        topics = []
        content_lower = content.lower()

        topic_keywords = {
            'machine_learning': ['neural', 'network', 'training', 'model', 'dataset'],
            'research': ['paper', 'study', 'journal', 'publication', 'author'],
            'programming': ['code', 'function', 'class', 'variable', 'algorithm'],
            'data_science': ['data', 'analysis', 'statistics', 'visualization'],
            'arxiv': ['arxiv', 'preprint', 'submission'],
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)

        return topics


class MemoryWritePipeline:
    """
    Complete pipeline for processing memories before storage.

    Combines filtering, enrichment, and scoring.
    """

    def __init__(self):
        """Initialize the write pipeline with all components."""
        self.filter = MemoryFilter()
        self.enricher = MemoryEnricher()
        self.scorer = SalienceScorer()

    def process_memory(
        self,
        content: str,
        role: str,
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Process a memory through the complete pipeline.

        Args:
            content: Memory content
            role: Message role
            metadata: Initial metadata
            user_context: User context for scoring

        Returns:
            dict[str, Any] | None: Processed memory data or None if filtered out
        """
        try:
            # Step 1: Filter
            should_store, filter_reason = self.filter.should_store(
                content, role, metadata
            )
            if not should_store:
                logger.debug(f'Memory filtered out: {filter_reason}')
                return None

            # Step 2: Enrich
            enriched_metadata = self.enricher.enrich(content, role, metadata)

            # Step 3: Score
            salience_score = self.scorer.calculate_salience(
                content, role, enriched_metadata, user_context
            )

            # Combine all data
            memory_data = {
                'content': content,
                'role': role,
                'metadata': enriched_metadata,
                'salience_score': salience_score,
                'pipeline_version': '1.0',
                'processed_at': datetime.now().isoformat(),
            }

            logger.info(
                f'Processed {role} memory with salience score: {salience_score:.3f}'
            )
            return memory_data

        except Exception as e:
            logger.error(f'Error in memory write pipeline: {e}')
            # Return basic memory data on error
            return {
                'content': content,
                'role': role,
                'metadata': metadata or {},
                'salience_score': 0.5,
                'error': str(e),
            }


class RelevanceScorer:
    """
    Score memories for relevance to a specific query or context.

    Used during retrieval to rank memories by relevance.
    """

    def __init__(self):
        """Initialize the relevance scorer."""
        # Boost factors for different types of matches
        self.exact_match_boost = 1.0
        self.partial_match_boost = 0.5
        self.semantic_match_boost = 0.3
        self.metadata_match_boost = 0.2

    def calculate_relevance(
        self,
        memory_content: str,
        memory_metadata: dict[str, Any],
        query: str,
        query_context: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate relevance score between memory and query.

        Args:
            memory_content: Stored memory content
            memory_metadata: Memory metadata
            query: Search query
            query_context: Additional query context

        Returns:
            float: Relevance score (0.0 to 1.0+, can exceed 1.0 with boosts)
        """
        try:
            score = 0.0
            query_lower = query.lower()
            content_lower = memory_content.lower()

            # Exact phrase match
            if query_lower in content_lower:
                score += self.exact_match_boost
                # Bonus for multiple occurrences
                occurrences = content_lower.count(query_lower)
                score += (occurrences - 1) * 0.1

            # Word-level matching
            query_words = set(query_lower.split())
            content_words = set(content_lower.split())
            common_words = query_words & content_words

            if common_words:
                # Percentage of query words found
                word_coverage = len(common_words) / len(query_words)
                score += word_coverage * self.partial_match_boost

            # Metadata matching
            if memory_metadata:
                # Topic matching
                memory_topics = memory_metadata.get('topics', [])
                if query_context:
                    query_topics = query_context.get('topics', [])
                    topic_overlap = set(memory_topics) & set(query_topics)
                    if topic_overlap:
                        score += len(topic_overlap) * 0.1

                # URL/DOI matching
                if 'urls' in memory_metadata or 'dois' in memory_metadata:
                    if any(
                        ref in query_lower
                        for ref in memory_metadata.get('urls', [])
                        + memory_metadata.get('dois', [])
                    ):
                        score += self.metadata_match_boost

                # Temporal relevance (recent memories slightly preferred)
                if 'timestamp' in memory_metadata:
                    try:
                        memory_time = datetime.fromisoformat(
                            memory_metadata['timestamp']
                        )
                        age_hours = (
                            datetime.now() - memory_time
                        ).total_seconds() / 3600
                        if age_hours < 24:  # Last 24 hours
                            score += 0.1
                        elif age_hours < 168:  # Last week
                            score += 0.05
                    except Exception:
                        pass

            # Role-based adjustments
            if memory_metadata.get('role') == 'user' and query_context:
                if query_context.get('prefer_user_content'):
                    score += 0.1

            # Salience interaction (highly salient memories get small boost)
            base_salience = memory_metadata.get('salience_score', 0.5)
            if base_salience > 0.8:
                score += 0.05

            logger.debug(f'Calculated relevance score: {score:.3f}')
            return score

        except Exception as e:
            logger.error(f'Error calculating relevance: {e}')
            return 0.0


class RetrievalRanker:
    """
    Rank and filter retrieved memories for optimal context.

    Combines relevance scoring with diversity and context limits.
    """

    def __init__(self, max_results: int = 10):
        """
        Initialize the retrieval ranker.

        Args:
            max_results: Maximum number of results to return
        """
        self.max_results = max_results
        self.relevance_scorer = RelevanceScorer()

        # Diversity parameters
        self.similarity_threshold = 0.8  # For deduplication
        self.topic_diversity_weight = 0.2

    def rank_memories(
        self,
        memories: list[dict[str, Any]],
        query: str,
        query_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rank and filter memories for retrieval.

        Args:
            memories: List of memory records
            query: Search query
            query_context: Query context

        Returns:
            list[dict[str, Any]]: Ranked and filtered memories
        """
        try:
            # Score all memories
            scored_memories = []
            for memory in memories:
                relevance = self.relevance_scorer.calculate_relevance(
                    memory.get('content', ''),
                    memory.get('metadata', {}),
                    query,
                    query_context,
                )

                # Combine with salience for final score
                salience = memory.get('salience_score', 0.5)
                combined_score = (0.7 * relevance) + (0.3 * salience)

                scored_memories.append(
                    {'memory': memory, 'relevance': relevance, 'score': combined_score}
                )

            # Sort by score
            scored_memories.sort(key=lambda x: x['score'], reverse=True)

            # Apply diversity filtering
            diverse_memories = self._ensure_diversity(scored_memories)

            # Take top results
            final_results = diverse_memories[: self.max_results]

            # Format output
            ranked_memories = []
            for item in final_results:
                memory = item['memory'].copy()
                memory['retrieval_score'] = item['score']
                memory['relevance_score'] = item['relevance']
                ranked_memories.append(memory)

            logger.info(
                f'Ranked {len(ranked_memories)} memories from {len(memories)} candidates'
            )
            return ranked_memories

        except Exception as e:
            logger.error(f'Error ranking memories: {e}')
            # Return original list on error
            return memories[: self.max_results]

    def _ensure_diversity(
        self, scored_memories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Ensure diversity in results by removing near-duplicates."""
        if not scored_memories:
            return []

        diverse = [scored_memories[0]]

        for candidate in scored_memories[1:]:
            is_duplicate = False

            # Check similarity with already selected memories
            for selected in diverse:
                similarity = self._calculate_similarity(
                    candidate['memory'], selected['memory']
                )
                if similarity > self.similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                diverse.append(candidate)

        return diverse

    def _calculate_similarity(
        self, memory1: dict[str, Any], memory2: dict[str, Any]
    ) -> float:
        """Calculate similarity between two memories."""
        # Simple content-based similarity
        content1 = memory1.get('content', '').lower()
        content2 = memory2.get('content', '').lower()

        if content1 == content2:
            return 1.0

        # Word overlap similarity
        words1 = set(content1.split())
        words2 = set(content2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)


class RetrievalMetrics:
    """
    Track and analyze retrieval performance metrics.

    Helps optimize retrieval strategies over time.
    """

    def __init__(self):
        """Initialize metrics tracking."""
        self.query_count = 0
        self.total_candidates = 0
        self.total_retrieved = 0
        self.relevance_scores: list[float] = []
        self.response_times: list[float] = []

        # Performance thresholds
        self.slow_query_threshold = 1.0  # seconds
        self.low_relevance_threshold = 0.3

    def record_retrieval(
        self,
        query: str,
        candidates_count: int,
        retrieved_count: int,
        relevance_scores: list[float],
        response_time: float,
    ) -> None:
        """
        Record metrics for a retrieval operation.

        Args:
            query: The search query
            candidates_count: Number of candidate memories
            retrieved_count: Number of retrieved memories
            relevance_scores: Relevance scores of retrieved memories
            response_time: Time taken for retrieval (seconds)
        """
        self.query_count += 1
        self.total_candidates += candidates_count
        self.total_retrieved += retrieved_count
        self.relevance_scores.extend(relevance_scores)
        self.response_times.append(response_time)

        # Log performance warnings
        if response_time > self.slow_query_threshold:
            logger.warning(
                f'Slow retrieval query ({response_time:.2f}s): "{query[:50]}..."'
            )

        avg_relevance = (
            sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        )
        if avg_relevance < self.low_relevance_threshold:
            logger.warning(
                f'Low relevance retrieval (avg: {avg_relevance:.3f}): "{query[:50]}..."'
            )

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary of retrieval metrics.

        Returns:
            dict[str, Any]: Metrics summary
        """
        if not self.query_count:
            return {'message': 'No retrieval operations recorded'}

        avg_candidates = self.total_candidates / self.query_count
        avg_retrieved = self.total_retrieved / self.query_count
        avg_relevance = (
            sum(self.relevance_scores) / len(self.relevance_scores)
            if self.relevance_scores
            else 0
        )
        avg_response_time = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times
            else 0
        )

        return {
            'total_queries': self.query_count,
            'avg_candidates_per_query': round(avg_candidates, 1),
            'avg_retrieved_per_query': round(avg_retrieved, 1),
            'avg_relevance_score': round(avg_relevance, 3),
            'avg_response_time_seconds': round(avg_response_time, 3),
            'slow_queries': sum(
                1 for t in self.response_times if t > self.slow_query_threshold
            ),
            'retrieval_ratio': round(
                self.total_retrieved / self.total_candidates if self.total_candidates else 0, 3
            ),
        }


class MemoryRetrievalPipeline:
    """
    Complete pipeline for retrieving memories.

    Handles search, ranking, and metric tracking.
    """

    def __init__(self, max_results: int = 10):
        """
        Initialize retrieval pipeline.

        Args:
            max_results: Maximum results to return
        """
        self.ranker = RetrievalRanker(max_results)
        self.metrics = RetrievalMetrics()

    def retrieve(
        self,
        query: str,
        candidate_memories: list[dict[str, Any]],
        query_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant memories for a query.

        Args:
            query: Search query
            candidate_memories: Pool of memories to search
            query_context: Additional query context

        Returns:
            list[dict[str, Any]]: Retrieved and ranked memories
        """
        start_time = datetime.now()

        try:
            # Rank memories
            ranked_memories = self.ranker.rank_memories(
                candidate_memories, query, query_context
            )

            # Record metrics
            response_time = (datetime.now() - start_time).total_seconds()
            relevance_scores = [
                m.get('relevance_score', 0.0) for m in ranked_memories
            ]

            self.metrics.record_retrieval(
                query,
                len(candidate_memories),
                len(ranked_memories),
                relevance_scores,
                response_time,
            )

            logger.info(
                f'Retrieved {len(ranked_memories)} memories in {response_time:.3f}s'
            )
            return ranked_memories

        except Exception as e:
            logger.error(f'Error in retrieval pipeline: {e}')
            # Return empty list on error
            return []

    def get_metrics(self) -> dict[str, Any]:
        """Get retrieval performance metrics."""
        return self.metrics.get_summary()


# Re-export all classes for backward compatibility
__all__ = [
    'SalienceScorer',
    'MemoryFilter',
    'MemoryEnricher',
    'MemoryWritePipeline',
    'RelevanceScorer',
    'RetrievalRanker',
    'RetrievalMetrics',
    'MemoryRetrievalPipeline',
]
