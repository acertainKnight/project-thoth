"""
Salience scoring for memory entries.

This module calculates importance scores for memories to determine retention priority.
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger


class SalienceScorer:
    """
    Calculate salience scores for memories to determine importance and retention.

    Higher scores indicate more important memories that should be retained longer.
    Score range: 0.0 (lowest) to 1.0 (highest)
    """

    def __init__(self):
        """Initialize the salience scorer with scoring criteria."""
        # Research-focused keywords get higher scores
        self.research_keywords = {
            'methodology',
            'findings',
            'results',
            'conclusion',
            'hypothesis',
            'experiment',
            'analysis',
            'discovery',
            'breakthrough',
            'novel',
            'significant',
            'important',
            'key',
            'critical',
            'essential',
            'arxiv',
            'paper',
            'study',
            'research',
            'publication',
            'journal',
            'doi',
            'citation',
            'author',
            'abstract',
            'introduction',
        }

        # Question words indicate important user interests
        self.question_indicators = {
            'what',
            'how',
            'why',
            'when',
            'where',
            'which',
            'who',
            'explain',
            'describe',
            'analyze',
            'compare',
            'evaluate',
        }

        # Action words suggest executable tasks
        self.action_keywords = {
            'create',
            'build',
            'generate',
            'analyze',
            'search',
            'find',
            'locate',
            'download',
            'process',
            'extract',
            'summarize',
        }

    def calculate_salience(
        self,
        content: str,
        role: str,
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate salience score for a memory entry.

        Args:
            content: Memory content text
            role: Message role (user, assistant, system)
            metadata: Additional metadata about the memory
            user_context: User context and preferences

        Returns:
            float: Salience score between 0.0 and 1.0
        """
        try:
            score = 0.0
            content_lower = content.lower()

            # Base score by role
            if role == 'user':
                score += 0.3  # User messages generally important
            elif role == 'assistant':
                score += 0.2  # Assistant responses moderately important
            elif role == 'system':
                score += 0.1  # System messages less important

            # Content length factor (moderate length preferred)
            length = len(content)
            if 20 <= length <= 500:
                score += 0.1
            elif 500 < length <= 1000:
                score += 0.05
            elif length > 2000:
                score -= 0.1  # Very long content may be less focused

            # Research keyword detection
            research_matches = sum(
                1 for keyword in self.research_keywords if keyword in content_lower
            )
            score += min(research_matches * 0.05, 0.2)  # Cap at 0.2

            # Question detection (indicates user interest)
            if any(q in content_lower for q in self.question_indicators):
                score += 0.15

            # Action keyword detection
            action_matches = sum(
                1 for keyword in self.action_keywords if keyword in content_lower
            )
            score += min(action_matches * 0.03, 0.1)  # Cap at 0.1

            # DOI or arXiv ID detection (academic content)
            if re.search(r'10\.\d+\/[\w\-\._]+|arXiv:\d+\.\d+', content):
                score += 0.15

            # URL detection (external references)
            if re.search(r'https?:\/\/[^\s]+', content):
                score += 0.05

            # Metadata-based scoring
            if metadata:
                # Tool calls indicate actionable content
                if metadata.get('tool_calls'):
                    score += 0.1

                # Error or failure states may be less important
                if metadata.get('error') or 'error' in content_lower:
                    score -= 0.1

                # Agent-specific metadata
                if metadata.get('agent_id'):
                    score += 0.05

            # User context considerations
            if user_context:
                # Recent activity indicates higher relevance
                last_activity = user_context.get('last_activity')
                if last_activity:
                    # Boost score for recent interactions
                    score += 0.05

                # User preferences
                preferences = user_context.get('preferences', {})
                focus_areas = preferences.get('research_focus', [])
                if focus_areas:
                    for area in focus_areas:
                        if area.lower() in content_lower:
                            score += 0.1
                            break

            # Normalize score to [0.0, 1.0] range
            final_score = max(0.0, min(1.0, score))

            logger.debug(
                f'Calculated salience score: {final_score:.3f} for {role} message'
            )
            return final_score

        except Exception as e:
            logger.error(f'Error calculating salience: {e}')
            # Return moderate score on error
            return 0.5