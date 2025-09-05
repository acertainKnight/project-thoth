"""
Memory filtering components for determining what memories to store.

This module provides filtering logic to decide which memories are worth
storing based on content quality, salience scores, and noise patterns.
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger


class MemoryFilter:
    """
    Filter memories based on various criteria before storage.
    """

    def __init__(self, min_salience: float = 0.1):
        """
        Initialize memory filter.

        Args:
            min_salience: Minimum salience score to retain memory
        """
        self.min_salience = min_salience

        # Content patterns to filter out
        self.noise_patterns = [
            r'^(ok|okay|yes|no|thanks?|thank you)\.?$',  # Simple acknowledgments
            r'^(hi|hello|hey)\.?$',  # Simple greetings
            r'^\s*$',  # Empty content
            r'^\.{3,}$',  # Just dots
            r'^-+$',  # Just dashes
        ]

    def should_store_memory(
        self,
        content: str,
        role: str,
        salience_score: float,
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> bool:
        """
        Determine if a memory should be stored.

        Args:
            content: Memory content
            role: Message role
            salience_score: Calculated salience score
            metadata: Memory metadata

        Returns:
            bool: True if memory should be stored
        """
        try:
            # Check salience threshold
            if salience_score < self.min_salience:
                logger.debug(
                    f'Memory filtered: salience {salience_score:.3f} < {self.min_salience}'
                )
                return False

            # Check content length
            if len(content.strip()) < 3:
                logger.debug('Memory filtered: content too short')
                return False

            # Check noise patterns
            content_clean = content.strip().lower()
            for pattern in self.noise_patterns:
                if re.match(pattern, content_clean):
                    logger.debug(f'Memory filtered: matches noise pattern {pattern}')
                    return False

            # Always store system errors for debugging
            if role == 'system' and (
                'error' in content.lower() or 'failed' in content.lower()
            ):
                logger.debug('Memory stored: system error/failure message')
                return True

            # Always store high-salience content
            if salience_score >= 0.8:
                logger.debug(f'Memory stored: high salience {salience_score:.3f}')
                return True

            logger.debug(f'Memory accepted: salience {salience_score:.3f}, role {role}')
            return True

        except Exception as e:
            logger.error(f'Error in memory filter: {e}')
            # Default to storing on error
            return True

    def filter_memory_batch(
        self,
        memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Filter a batch of memories.

        Args:
            memories: List of memory dictionaries with 'content', 'role',
                     'salience_score', and optional 'metadata' keys

        Returns:
            list[dict]: Filtered list of memories that should be stored
        """
        filtered_memories = []

        for memory in memories:
            content = memory.get('content', '')
            role = memory.get('role', 'unknown')
            salience_score = memory.get('salience_score', 0.0)
            metadata = memory.get('metadata')

            if self.should_store_memory(content, role, salience_score, metadata):
                filtered_memories.append(memory)

        logger.info(f'Filtered {len(memories)} memories to {len(filtered_memories)}')
        return filtered_memories

    def update_noise_patterns(self, new_patterns: list[str]) -> None:
        """
        Update the noise patterns used for filtering.

        Args:
            new_patterns: List of regex patterns to add to noise filtering
        """
        self.noise_patterns.extend(new_patterns)
        logger.info(f'Added {len(new_patterns)} new noise patterns')

    def set_min_salience(self, min_salience: float) -> None:
        """
        Update the minimum salience threshold.

        Args:
            min_salience: New minimum salience score (0.0 to 1.0)
        """
        self.min_salience = max(0.0, min(1.0, min_salience))
        logger.info(f'Updated minimum salience threshold to {self.min_salience}')

    def get_filter_stats(self, memories: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Get statistics about what would be filtered from a memory set.

        Args:
            memories: List of memory dictionaries to analyze

        Returns:
            dict: Statistics about filtering results
        """
        stats = {
            'total_memories': len(memories),
            'would_store': 0,
            'filtered_by_salience': 0,
            'filtered_by_length': 0,
            'filtered_by_noise': 0,
            'stored_as_high_salience': 0,
            'stored_as_system_error': 0,
        }

        for memory in memories:
            content = memory.get('content', '')
            role = memory.get('role', 'unknown')
            salience_score = memory.get('salience_score', 0.0)

            # Simulate filtering logic
            if salience_score < self.min_salience:
                stats['filtered_by_salience'] += 1
            elif len(content.strip()) < 3:
                stats['filtered_by_length'] += 1
            elif any(
                re.match(pattern, content.strip().lower())
                for pattern in self.noise_patterns
            ):
                stats['filtered_by_noise'] += 1
            else:
                stats['would_store'] += 1

                if salience_score >= 0.8:
                    stats['stored_as_high_salience'] += 1
                elif role == 'system' and (
                    'error' in content.lower() or 'failed' in content.lower()
                ):
                    stats['stored_as_system_error'] += 1

        return stats
