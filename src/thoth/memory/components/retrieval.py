"""
Memory retrieval components for ranking and performance tracking.

This module provides functionality for ranking retrieved memories
and tracking retrieval performance metrics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger


class RetrievalRanker:
    """
    Rank and filter retrieved memories based on multiple factors.

    Combines relevance, salience, recency, and user preferences
    to produce optimal memory ranking for retrieval.
    """

    def __init__(
        self,
        relevance_weight: float = 0.4,
        salience_weight: float = 0.3,
        recency_weight: float = 0.2,
        diversity_weight: float = 0.1,
    ):
        """
        Initialize the retrieval ranker.

        Args:
            relevance_weight: Weight for relevance scores
            salience_weight: Weight for salience scores
            recency_weight: Weight for recency scores
            diversity_weight: Weight for diversity scores
        """
        self.relevance_weight = relevance_weight
        self.salience_weight = salience_weight
        self.recency_weight = recency_weight
        self.diversity_weight = diversity_weight

        # Ensure weights sum to 1.0
        total_weight = sum(
            [relevance_weight, salience_weight, recency_weight, diversity_weight]
        )
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f'Ranking weights sum to {total_weight}, normalizing to 1.0')
            self.relevance_weight /= total_weight
            self.salience_weight /= total_weight
            self.recency_weight /= total_weight
            self.diversity_weight /= total_weight

    def rank_memories(
        self,
        memories: list[dict[str, Any]],
        query: str,
        user_preferences: dict[str, Any] | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Rank memories by relevance and other factors.

        Args:
            memories: List of memories with relevance scores
            query: Original search query
            user_preferences: User-specific ranking preferences
            max_results: Maximum number of results to return

        Returns:
            List of ranked memories with ranking scores
        """
        if not memories:
            return []

        try:
            # Calculate composite scores for all memories
            scored_memories = []
            for memory in memories:
                composite_score = self._calculate_composite_score(
                    memory, user_preferences
                )
                memory['_ranking_score'] = composite_score
                scored_memories.append(memory)

            # Sort by composite score
            scored_memories.sort(key=lambda x: x['_ranking_score'], reverse=True)

            # Apply diversity filtering
            diverse_memories = self._apply_diversity_filter(scored_memories, query)

            # Return top results
            return diverse_memories[:max_results]

        except Exception as e:
            logger.error(f'Memory ranking failed: {e}')
            return memories[:max_results]

    def _calculate_composite_score(
        self, memory: dict[str, Any], user_preferences: dict[str, Any] | None
    ) -> float:
        """Calculate composite ranking score."""
        # Get individual scores
        relevance = memory.get('_relevance_score', 0.5)
        salience = memory.get('salience_score', 0.5)
        recency = self._calculate_recency_score(memory)
        diversity = memory.get('_diversity_score', 0.5)

        # Apply user preferences
        if user_preferences:
            relevance = self._apply_user_preferences(
                relevance, memory, user_preferences
            )

        # Calculate weighted composite score
        composite = (
            (relevance * self.relevance_weight)
            + (salience * self.salience_weight)
            + (recency * self.recency_weight)
            + (diversity * self.diversity_weight)
        )

        return min(1.0, max(0.0, composite))

    def _calculate_recency_score(self, memory: dict[str, Any]) -> float:
        """Calculate recency score based on creation time."""
        created_at = memory.get('created_at')
        if not created_at:
            return 0.5

        try:
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(created_time.tzinfo)

            # Calculate hours since creation
            hours_old = (now - created_time).total_seconds() / 3600

            # Recent memories get higher scores
            if hours_old < 1:
                return 1.0
            elif hours_old < 24:
                return 0.9
            elif hours_old < 168:  # 1 week
                return 0.7
            elif hours_old < 720:  # 1 month
                return 0.5
            else:
                return 0.3

        except Exception:
            return 0.5

    def _apply_user_preferences(
        self, base_score: float, memory: dict[str, Any], preferences: dict[str, Any]
    ) -> float:
        """Apply user preferences to adjust scoring."""
        adjusted_score = base_score

        # Preferred content types
        preferred_types = preferences.get('content_types', [])
        memory_type = memory.get('metadata', {}).get('content_type')
        if preferred_types and memory_type in preferred_types:
            adjusted_score = min(1.0, adjusted_score * 1.1)

        # Research field preferences
        preferred_fields = preferences.get('research_fields', [])
        memory_fields = memory.get('metadata', {}).get('research_fields', [])
        if preferred_fields and any(
            field in memory_fields for field in preferred_fields
        ):
            adjusted_score = min(1.0, adjusted_score * 1.05)

        return adjusted_score

    def _apply_diversity_filter(
        self,
        memories: list[dict[str, Any]],
        query: str,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Apply diversity filtering to avoid redundant results."""
        if len(memories) <= 3:
            return memories

        diverse_memories = []
        seen_content_hashes = set()

        for memory in memories:
            content = memory.get('content', '')
            content_hash = hash(content.lower().strip())

            # Skip very similar content
            if content_hash not in seen_content_hashes:
                diverse_memories.append(memory)
                seen_content_hashes.add(content_hash)

                # Stop if we have enough diverse results
                if len(diverse_memories) >= len(memories) * 0.8:
                    break

        return diverse_memories

    def update_weights(
        self,
        relevance_weight: float | None = None,
        salience_weight: float | None = None,
        recency_weight: float | None = None,
        diversity_weight: float | None = None,
    ) -> None:
        """
        Update ranking weights dynamically.

        Args:
            relevance_weight: New relevance weight
            salience_weight: New salience weight
            recency_weight: New recency weight
            diversity_weight: New diversity weight
        """
        if relevance_weight is not None:
            self.relevance_weight = relevance_weight
        if salience_weight is not None:
            self.salience_weight = salience_weight
        if recency_weight is not None:
            self.recency_weight = recency_weight
        if diversity_weight is not None:
            self.diversity_weight = diversity_weight

        # Normalize weights
        total_weight = sum(
            [
                self.relevance_weight,
                self.salience_weight,
                self.recency_weight,
                self.diversity_weight,
            ]
        )

        if total_weight > 0:
            self.relevance_weight /= total_weight
            self.salience_weight /= total_weight
            self.recency_weight /= total_weight
            self.diversity_weight /= total_weight

        logger.info(
            f'Updated ranking weights: R={self.relevance_weight:.2f}, S={self.salience_weight:.2f}, T={self.recency_weight:.2f}, D={self.diversity_weight:.2f}'
        )


class RetrievalMetrics:
    """
    Track and analyze memory retrieval performance metrics.

    Provides insights into search quality, user satisfaction,
    and system performance for continuous improvement.
    """

    def __init__(self):
        """Initialize retrieval metrics tracker."""
        self.query_metrics: dict[str, Any] = {}
        self.session_stats: dict[str, Any] = {}

    def record_query(
        self,
        query: str,
        results_count: int,
        response_time_ms: float,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        Record metrics for a search query.

        Args:
            query: Search query text
            results_count: Number of results returned
            response_time_ms: Response time in milliseconds
            user_id: User identifier
            session_id: Session identifier
        """
        timestamp = datetime.now().isoformat()

        query_metric = {
            'query': query,
            'results_count': results_count,
            'response_time_ms': response_time_ms,
            'timestamp': timestamp,
            'user_id': user_id,
            'session_id': session_id,
        }

        # Store individual query metric
        query_id = hash(f'{query}{timestamp}{user_id}')
        self.query_metrics[query_id] = query_metric

        # Update session stats
        if session_id:
            if session_id not in self.session_stats:
                self.session_stats[session_id] = {
                    'query_count': 0,
                    'total_response_time': 0.0,
                    'total_results': 0,
                    'first_query': timestamp,
                    'last_query': timestamp,
                }

            stats = self.session_stats[session_id]
            stats['query_count'] += 1
            stats['total_response_time'] += response_time_ms
            stats['total_results'] += results_count
            stats['last_query'] = timestamp

        logger.debug(
            f'Recorded query metric: {results_count} results in {response_time_ms:.1f}ms'
        )

    def record_user_feedback(
        self,
        query: str,
        result_rank: int,
        feedback_type: str,  # 'click', 'like', 'dislike', 'irrelevant'
        user_id: str | None = None,
    ) -> None:
        """
        Record user feedback on search results.

        Args:
            query: Original search query
            result_rank: Rank of the result (0-based)
            feedback_type: Type of feedback
            user_id: User identifier
        """
        feedback = {
            'query': query,
            'result_rank': result_rank,
            'feedback_type': feedback_type,
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
        }

        # Store feedback (implement storage mechanism as needed)
        # TODO: Implement actual feedback storage using feedback dict
        logger.info(
            f'User feedback recorded: {feedback["feedback_type"]} on rank {feedback["result_rank"]} for query "{feedback["query"]}"'
        )

    def get_query_stats(self) -> dict[str, Any]:
        """Get aggregated query statistics."""
        if not self.query_metrics:
            return {}

        metrics = list(self.query_metrics.values())
        response_times = [m['response_time_ms'] for m in metrics]
        result_counts = [m['results_count'] for m in metrics]

        stats = {
            'total_queries': len(metrics),
            'avg_response_time_ms': sum(response_times) / len(response_times),
            'avg_results_count': sum(result_counts) / len(result_counts),
            'queries_with_results': len([c for c in result_counts if c > 0]),
            'zero_result_queries': len([c for c in result_counts if c == 0]),
        }

        return stats

    def get_session_stats(self, session_id: str) -> dict[str, Any] | None:
        """Get statistics for a specific session."""
        return self.session_stats.get(session_id)

    def get_performance_summary(self) -> dict[str, Any]:
        """Get overall performance summary."""
        query_stats = self.get_query_stats()

        summary = {
            'query_performance': query_stats,
            'active_sessions': len(self.session_stats),
            'total_session_queries': sum(
                s['query_count'] for s in self.session_stats.values()
            ),
        }

        # Add response time percentiles if we have data
        if self.query_metrics:
            response_times = sorted(
                [m['response_time_ms'] for m in self.query_metrics.values()]
            )
            if response_times:
                n = len(response_times)
                summary['response_time_percentiles'] = {
                    'p50': response_times[n // 2],
                    'p95': response_times[int(n * 0.95)]
                    if n > 20
                    else response_times[-1],
                    'p99': response_times[int(n * 0.99)]
                    if n > 100
                    else response_times[-1],
                }

        return summary

    def clear_old_metrics(self, days_to_keep: int = 7) -> None:
        """
        Clear metrics older than specified days.

        Args:
            days_to_keep: Number of days of metrics to retain
        """
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)

        # Clear old query metrics
        old_query_ids = []
        for query_id, metric in self.query_metrics.items():
            try:
                metric_time = datetime.fromisoformat(metric['timestamp']).timestamp()
                if metric_time < cutoff_time:
                    old_query_ids.append(query_id)
            except (ValueError, KeyError):
                old_query_ids.append(query_id)  # Remove malformed entries

        for query_id in old_query_ids:
            del self.query_metrics[query_id]

        logger.info(f'Cleared {len(old_query_ids)} old query metrics')
