"""
Memory Summarization Module

This module provides intelligent summarization of episodic memories,
transferring important information to archival storage while maintaining
context and reducing memory fragmentation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


class EpisodicSummarizer:
    """
    Intelligent summarizer for episodic memories.

    Analyzes patterns in episodic memories, identifies key themes,
    and generates coherent summaries for archival storage.
    """

    def __init__(
        self,
        theme_threshold: float = 0.3,
        min_memories_for_summary: int = 3,
        max_summary_length: int = 500,
    ):
        """
        Initialize the episodic summarizer.

        Args:
            theme_threshold: Threshold for theme clustering (0.0-1.0)
            min_memories_for_summary: Minimum memories needed for summarization
            max_summary_length: Maximum character length for generated summaries
        """
        self.theme_threshold = theme_threshold
        self.min_memories_for_summary = min_memories_for_summary
        self.max_summary_length = max_summary_length

        # Topic detection patterns
        self.topic_patterns = {
            'research': [
                r'(research|study|analysis|methodology)',
                r'(paper|article|publication|journal)',
                r'(experiment|data|results|findings)',
                r'(theory|hypothesis|approach|technique)',
            ],
            'technology': [
                r'(algorithm|framework|system|architecture)',
                r'(implementation|development|coding|programming)',
                r'(performance|optimization|efficiency)',
                r'(neural|machine learning|AI|artificial intelligence)',
            ],
            'discussion': [
                r'(question|answer|clarification|explanation)',
                r'(conversation|dialogue|discussion|chat)',
                r'(help|assist|support|guidance)',
                r'(understand|learn|know|figure out)',
            ],
            'task': [
                r'(task|project|work|assignment)',
                r'(todo|plan|goal|objective)',
                r'(deadline|timeline|schedule)',
                r'(complete|finish|done|accomplish)',
            ],
        }

        logger.info('EpisodicSummarizer initialized')

    def analyze_memories(
        self,
        memories: list[dict[str, Any]],
        analysis_window_hours: int = 168,  # 1 week default
    ) -> dict[str, Any]:
        """
        Analyze episodic memories to identify patterns and themes.

        Args:
            memories: List of episodic memory entries
            analysis_window_hours: Time window for analysis in hours

        Returns:
            Dict with analysis results including themes, patterns, and statistics
        """
        try:
            if len(memories) < self.min_memories_for_summary:
                return {
                    'status': 'insufficient_memories',
                    'memory_count': len(memories),
                    'min_required': self.min_memories_for_summary,
                }

            # Filter memories within time window
            cutoff_time = datetime.now() - timedelta(hours=analysis_window_hours)
            recent_memories = [
                memory
                for memory in memories
                if self._is_recent_memory(memory, cutoff_time)
            ]

            if not recent_memories:
                return {
                    'status': 'no_recent_memories',
                    'total_memories': len(memories),
                    'cutoff_time': cutoff_time.isoformat(),
                }

            # Analyze memory patterns
            themes = self._identify_themes(recent_memories)
            temporal_patterns = self._analyze_temporal_patterns(recent_memories)
            interaction_patterns = self._analyze_interaction_patterns(recent_memories)
            salience_distribution = self._analyze_salience_distribution(recent_memories)

            analysis = {
                'status': 'success',
                'analysis_period': {
                    'start_time': cutoff_time.isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'window_hours': analysis_window_hours,
                },
                'memory_stats': {
                    'total_memories': len(memories),
                    'analyzed_memories': len(recent_memories),
                    'avg_salience': sum(
                        m.get('salience_score', 0) for m in recent_memories
                    )
                    / len(recent_memories),
                    'high_salience_count': len(
                        [
                            m
                            for m in recent_memories
                            if m.get('salience_score', 0) >= 0.7
                        ]
                    ),
                },
                'themes': themes,
                'temporal_patterns': temporal_patterns,
                'interaction_patterns': interaction_patterns,
                'salience_distribution': salience_distribution,
                'summarizable_themes': [
                    theme_name
                    for theme_name, theme_data in themes.items()
                    if len(theme_data['memories']) >= self.min_memories_for_summary
                ],
            }

            logger.info(
                f'Memory analysis completed: {len(recent_memories)} memories, {len(themes)} themes identified'
            )
            return analysis

        except Exception as e:
            logger.error(f'Memory analysis failed: {e}')
            return {'status': 'error', 'message': str(e)}

    def generate_summaries(
        self, memories: list[dict[str, Any]], analysis_result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Generate summaries from analyzed memories.

        Args:
            memories: Original episodic memories
            analysis_result: Result from analyze_memories()

        Returns:
            List of summary dictionaries ready for archival storage
        """
        try:
            if analysis_result.get('status') != 'success':
                return []

            summaries = []
            themes = analysis_result.get('themes', {})

            for theme_name in analysis_result.get('summarizable_themes', []):
                theme_data = themes[theme_name]
                theme_memories = theme_data['memories']

                if len(theme_memories) >= self.min_memories_for_summary:
                    summary = self._generate_theme_summary(
                        theme_name, theme_memories, theme_data
                    )
                    if summary:
                        summaries.append(summary)

            # Generate temporal summary for high-activity periods
            temporal_summary = self._generate_temporal_summary(
                memories, analysis_result.get('temporal_patterns', {})
            )
            if temporal_summary:
                summaries.append(temporal_summary)

            logger.info(f'Generated {len(summaries)} summaries from memory analysis')
            return summaries

        except Exception as e:
            logger.error(f'Summary generation failed: {e}')
            return []

    def _is_recent_memory(self, memory: dict[str, Any], cutoff_time: datetime) -> bool:
        """Check if memory is within the analysis window."""
        created_at = memory.get('created_at')
        if not created_at:
            return False

        try:
            memory_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            return memory_time >= cutoff_time
        except Exception:
            return False

    def _identify_themes(self, memories: list[dict[str, Any]]) -> dict[str, Any]:
        """Identify themes in memories using pattern matching."""
        themes = defaultdict(
            lambda: {'memories': [], 'strength': 0.0, 'keywords': set()}
        )

        for memory in memories:
            content = memory.get('content', '').lower()
            memory_themes = []

            # Check for topic patterns
            for topic, patterns in self.topic_patterns.items():
                matches = sum(
                    len(re.findall(pattern, content, re.IGNORECASE))
                    for pattern in patterns
                )
                if matches > 0:
                    themes[topic]['memories'].append(memory)
                    themes[topic]['strength'] += matches * memory.get(
                        'salience_score', 0.5
                    )
                    memory_themes.append(topic)

                    # Extract keywords
                    for pattern in patterns:
                        for match in re.finditer(pattern, content, re.IGNORECASE):
                            themes[topic]['keywords'].add(match.group().lower())

            # Handle memories without clear themes
            if not memory_themes and memory.get('salience_score', 0) >= 0.6:
                themes['miscellaneous']['memories'].append(memory)
                themes['miscellaneous']['strength'] += memory.get('salience_score', 0.5)

        # Convert keywords sets to lists and normalize strength
        for _theme_name, theme_data in themes.items():
            theme_data['keywords'] = list(theme_data['keywords'])[
                :10
            ]  # Top 10 keywords
            if theme_data['memories']:
                theme_data['strength'] = theme_data['strength'] / len(
                    theme_data['memories']
                )

        return dict(themes)

    def _analyze_temporal_patterns(
        self, memories: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze temporal patterns in memory creation."""
        if not memories:
            return {}

        # Group memories by day and hour
        daily_counts = defaultdict(int)
        hourly_counts = defaultdict(int)

        for memory in memories:
            created_at = memory.get('created_at')
            if not created_at:
                continue

            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                daily_counts[dt.strftime('%Y-%m-%d')] += 1
                hourly_counts[dt.hour] += 1
            except Exception:
                continue

        # Find peak activity periods
        peak_day = (
            max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else None
        )
        peak_hour = (
            max(hourly_counts.items(), key=lambda x: x[1]) if hourly_counts else None
        )

        return {
            'daily_distribution': dict(daily_counts),
            'hourly_distribution': dict(hourly_counts),
            'peak_day': peak_day[0] if peak_day else None,
            'peak_day_count': peak_day[1] if peak_day else 0,
            'peak_hour': peak_hour[0] if peak_hour else None,
            'peak_hour_count': peak_hour[1] if peak_hour else 0,
            'total_active_days': len(daily_counts),
            'avg_memories_per_day': len(memories) / max(1, len(daily_counts)),
        }

    def _analyze_interaction_patterns(
        self, memories: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze user interaction patterns."""
        role_counts = defaultdict(int)
        content_types = defaultdict(int)

        for memory in memories:
            role = memory.get('role', 'unknown')
            role_counts[role] += 1

            content_type = memory.get('metadata', {}).get('content_type', 'general')
            content_types[content_type] += 1

        return {
            'role_distribution': dict(role_counts),
            'content_type_distribution': dict(content_types),
            'dominant_role': max(role_counts.items(), key=lambda x: x[1])[0]
            if role_counts
            else None,
            'dominant_content_type': max(content_types.items(), key=lambda x: x[1])[0]
            if content_types
            else None,
        }

    def _analyze_salience_distribution(
        self, memories: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze the distribution of salience scores."""
        salience_scores = [
            m.get('salience_score', 0)
            for m in memories
            if m.get('salience_score') is not None
        ]

        if not salience_scores:
            return {}

        # Calculate distribution buckets
        high_salience = [s for s in salience_scores if s >= 0.7]
        medium_salience = [s for s in salience_scores if 0.4 <= s < 0.7]
        low_salience = [s for s in salience_scores if s < 0.4]

        return {
            'mean_salience': sum(salience_scores) / len(salience_scores),
            'max_salience': max(salience_scores),
            'min_salience': min(salience_scores),
            'high_salience_count': len(high_salience),
            'medium_salience_count': len(medium_salience),
            'low_salience_count': len(low_salience),
            'distribution': {
                'high': len(high_salience) / len(salience_scores),
                'medium': len(medium_salience) / len(salience_scores),
                'low': len(low_salience) / len(salience_scores),
            },
        }

    def _generate_theme_summary(
        self,
        theme_name: str,
        memories: list[dict[str, Any]],
        theme_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generate a summary for a specific theme."""
        try:
            if len(memories) < self.min_memories_for_summary:
                return None

            # Sort memories by salience and recency
            sorted_memories = sorted(
                memories,
                key=lambda m: (m.get('salience_score', 0), m.get('created_at', '')),
                reverse=True,
            )

            # Extract key content from top memories
            key_points = []
            for memory in sorted_memories[:5]:  # Top 5 memories
                content = memory.get('content', '').strip()
                if content and len(content) > 20:  # Meaningful content
                    # Truncate long content
                    if len(content) > 150:
                        content = content[:147] + '...'
                    key_points.append(content)

            # Generate summary text
            summary_text = self._create_summary_text(theme_name, key_points, theme_data)

            # Calculate summary metadata
            total_salience = sum(m.get('salience_score', 0) for m in memories)
            avg_salience = total_salience / len(memories)

            # Find time range
            dates = [m.get('created_at') for m in memories if m.get('created_at')]
            start_date = min(dates) if dates else datetime.now().isoformat()
            end_date = max(dates) if dates else datetime.now().isoformat()

            return {
                'theme': theme_name,
                'content': summary_text,
                'summary_type': 'theme_summary',
                'source_memories_count': len(memories),
                'avg_salience': avg_salience,
                'total_salience': total_salience,
                'time_period': {'start': start_date, 'end': end_date},
                'keywords': theme_data.get('keywords', [])[:5],
                'created_at': datetime.now().isoformat(),
                'metadata': {
                    'content_type': 'summary',
                    'summary_theme': theme_name,
                    'source_memory_ids': [m.get('id') for m in memories if m.get('id')],
                    'summarization_method': 'theme_based',
                },
            }

        except Exception as e:
            logger.error(f'Theme summary generation failed for {theme_name}: {e}')
            return None

    def _generate_temporal_summary(
        self, memories: list[dict[str, Any]], temporal_patterns: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Generate a summary based on temporal activity patterns."""
        try:
            peak_day = temporal_patterns.get('peak_day')
            peak_day_count = temporal_patterns.get('peak_day_count', 0)

            if not peak_day or peak_day_count < self.min_memories_for_summary:
                return None

            # Find memories from the peak day
            peak_day_memories = [
                m for m in memories if m.get('created_at', '').startswith(peak_day)
            ]

            if len(peak_day_memories) < self.min_memories_for_summary:
                return None

            # Generate summary for peak activity day
            high_salience_memories = [
                m for m in peak_day_memories if m.get('salience_score', 0) >= 0.6
            ]

            summary_memories = (
                high_salience_memories
                if high_salience_memories
                else peak_day_memories[:5]
            )

            summary_text = (
                f'High activity day ({peak_day}) with {peak_day_count} interactions. '
            )
            key_interactions = []

            for memory in summary_memories:
                content = memory.get('content', '').strip()
                if content and len(content) > 15:
                    if len(content) > 100:
                        content = content[:97] + '...'
                    key_interactions.append(content)

            if key_interactions:
                summary_text += (
                    f'Key interactions included: {"; ".join(key_interactions[:3])}.'
                )

            return {
                'theme': 'high_activity_period',
                'content': summary_text,
                'summary_type': 'temporal_summary',
                'source_memories_count': len(peak_day_memories),
                'avg_salience': sum(
                    m.get('salience_score', 0) for m in peak_day_memories
                )
                / len(peak_day_memories),
                'time_period': {
                    'start': f'{peak_day}T00:00:00',
                    'end': f'{peak_day}T23:59:59',
                },
                'created_at': datetime.now().isoformat(),
                'metadata': {
                    'content_type': 'summary',
                    'summary_theme': 'temporal_activity',
                    'peak_activity_day': peak_day,
                    'activity_count': peak_day_count,
                    'source_memory_ids': [
                        m.get('id') for m in peak_day_memories if m.get('id')
                    ],
                    'summarization_method': 'temporal_based',
                },
            }

        except Exception as e:
            logger.error(f'Temporal summary generation failed: {e}')
            return None

    def _create_summary_text(
        self, theme_name: str, key_points: list[str], theme_data: dict[str, Any]
    ) -> str:
        """Create coherent summary text from key points."""
        if not key_points:
            return f'Summary of {theme_name.replace("_", " ")} activities with no detailed content available.'

        # Start with theme introduction
        summary_parts = [f'Summary of {theme_name.replace("_", " ")} activities:']

        # Add key points
        for i, point in enumerate(key_points[:3], 1):  # Limit to top 3 points
            summary_parts.append(f'{i}. {point}')

        # Add keyword context if available
        keywords = theme_data.get('keywords', [])[:3]
        if keywords:
            summary_parts.append(f'Key topics: {", ".join(keywords)}')

        summary_text = ' '.join(summary_parts)

        # Truncate if too long
        if len(summary_text) > self.max_summary_length:
            summary_text = summary_text[: self.max_summary_length - 3] + '...'

        return summary_text


class MemorySummarizationJob:
    """
    Scheduled job for episodic memory summarization.

    Integrates with the scheduler system to periodically analyze
    episodic memories and create archival summaries.
    """

    def __init__(
        self,
        memory_store,
        summarizer: EpisodicSummarizer | None = None,
        analysis_window_hours: int = 168,  # 1 week
        min_memories_threshold: int = 10,
        cleanup_after_summary: bool = False,
    ):
        """
        Initialize the memory summarization job.

        Args:
            memory_store: ThothMemoryStore instance
            summarizer: EpisodicSummarizer instance (creates default if None)
            analysis_window_hours: Time window for memory analysis
            min_memories_threshold: Minimum memories before running summarization
            cleanup_after_summary: Whether to remove summarized memories
        """
        self.memory_store = memory_store
        self.summarizer = summarizer or EpisodicSummarizer()
        self.analysis_window_hours = analysis_window_hours
        self.min_memories_threshold = min_memories_threshold
        self.cleanup_after_summary = cleanup_after_summary

        logger.info('Memory summarization job initialized')

    def run_summarization(self, user_id: str) -> dict[str, Any]:
        """
        Run memory summarization for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Dict with summarization results and statistics
        """
        try:
            logger.info(f'Starting memory summarization for user {user_id}')

            # Get episodic memories
            episodic_memories = self.memory_store.read_memories(
                user_id=user_id,
                scope='episodic',
                limit=1000,  # Large limit to get all recent memories
            )

            if len(episodic_memories) < self.min_memories_threshold:
                return {
                    'status': 'insufficient_memories',
                    'user_id': user_id,
                    'memory_count': len(episodic_memories),
                    'min_required': self.min_memories_threshold,
                }

            # Analyze memories
            analysis_result = self.summarizer.analyze_memories(
                episodic_memories, self.analysis_window_hours
            )

            if analysis_result.get('status') != 'success':
                return {
                    'status': 'analysis_failed',
                    'user_id': user_id,
                    'analysis_result': analysis_result,
                }

            # Generate summaries
            summaries = self.summarizer.generate_summaries(
                episodic_memories, analysis_result
            )

            # Store summaries in archival scope
            stored_summaries = []
            for summary in summaries:
                summary_id = self.memory_store.write_memory(
                    user_id=user_id,
                    content=summary['content'],
                    role='system',
                    scope='archival',
                    metadata=summary.get('metadata', {}),
                    salience_score=summary.get('avg_salience', 0.7),
                )

                if summary_id:
                    stored_summaries.append(
                        {
                            'id': summary_id,
                            'theme': summary.get('theme'),
                            'type': summary.get('summary_type'),
                            'source_memories': summary.get('source_memories_count', 0),
                        }
                    )

            # Optional cleanup of old episodic memories
            cleaned_memories = 0
            if self.cleanup_after_summary and stored_summaries:
                cleaned_memories = self._cleanup_summarized_memories(
                    user_id, summaries, episodic_memories
                )

            result = {
                'status': 'success',
                'user_id': user_id,
                'summaries_created': len(stored_summaries),
                'memories_analyzed': len(episodic_memories),
                'memories_cleaned': cleaned_memories,
                'analysis_window_hours': self.analysis_window_hours,
                'themes_identified': len(analysis_result.get('themes', {})),
                'summaries': stored_summaries,
                'execution_time': datetime.now().isoformat(),
            }

            logger.info(
                f'Memory summarization completed for user {user_id}: '
                f'{len(stored_summaries)} summaries created from '
                f'{len(episodic_memories)} memories'
            )

            return result

        except Exception as e:
            logger.error(f'Memory summarization failed for user {user_id}: {e}')
            return {
                'status': 'error',
                'user_id': user_id,
                'message': str(e),
                'execution_time': datetime.now().isoformat(),
            }

    def run_for_all_users(self) -> dict[str, Any]:
        """
        Run summarization for all users with episodic memories.

        Returns:
            Dict with aggregated results for all users
        """
        try:
            logger.info('Starting memory summarization for all users')

            # Get all users with episodic memories
            # Note: This is a simplified approach - in a real system,
            # you'd want a more efficient way to identify active users
            user_ids = self._get_users_with_episodic_memories()

            if not user_ids:
                return {
                    'status': 'no_users_found',
                    'total_users': 0,
                    'execution_time': datetime.now().isoformat(),
                }

            results = {}
            total_summaries = 0
            successful_users = 0
            failed_users = 0

            for user_id in user_ids:
                try:
                    user_result = self.run_summarization(user_id)
                    results[user_id] = user_result

                    if user_result.get('status') == 'success':
                        successful_users += 1
                        total_summaries += user_result.get('summaries_created', 0)
                    else:
                        failed_users += 1

                except Exception as e:
                    logger.error(f'Summarization failed for user {user_id}: {e}')
                    results[user_id] = {'status': 'error', 'message': str(e)}
                    failed_users += 1

            return {
                'status': 'completed',
                'total_users': len(user_ids),
                'successful_users': successful_users,
                'failed_users': failed_users,
                'total_summaries_created': total_summaries,
                'user_results': results,
                'execution_time': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f'Batch memory summarization failed: {e}')
            return {
                'status': 'error',
                'message': str(e),
                'execution_time': datetime.now().isoformat(),
            }

    def _get_users_with_episodic_memories(self) -> list[str]:
        """Get list of user IDs that have episodic memories."""
        # This is a simplified implementation
        # In a real system, you'd query the memory store more efficiently
        try:
            # For now, return a placeholder - this would need to be implemented
            # based on the actual memory store's capability to list users
            return []
        except Exception as e:
            logger.error(f'Failed to get users with episodic memories: {e}')
            return []

    def _cleanup_summarized_memories(
        self,
        user_id: str,
        summaries: list[dict[str, Any]],
        episodic_memories: list[dict[str, Any]],
    ) -> int:
        """Clean up episodic memories that have been summarized."""
        if not self.cleanup_after_summary:
            return 0

        try:
            # Collect IDs of memories that were included in summaries
            summarized_memory_ids = set()
            for summary in summaries:
                source_ids = summary.get('metadata', {}).get('source_memory_ids', [])
                summarized_memory_ids.update(source_ids)

            # Delete summarized memories that are older than threshold
            cutoff_date = datetime.now() - timedelta(
                hours=self.analysis_window_hours * 2
            )
            cleaned_count = 0

            for memory in episodic_memories:
                memory_id = memory.get('id')
                if not memory_id or memory_id not in summarized_memory_ids:
                    continue

                # Check if memory is old enough to clean up
                created_at = memory.get('created_at')
                if created_at:
                    try:
                        memory_date = datetime.fromisoformat(
                            created_at.replace('Z', '+00:00')
                        )
                        if memory_date < cutoff_date:
                            success = self.memory_store.delete_memory(
                                memory_id, user_id, 'episodic'
                            )
                            if success:
                                cleaned_count += 1
                    except Exception:
                        continue

            logger.info(
                f'Cleaned up {cleaned_count} summarized memories for user {user_id}'
            )
            return cleaned_count

        except Exception as e:
            logger.error(f'Memory cleanup failed for user {user_id}: {e}')
            return 0
