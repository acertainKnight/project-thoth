"""
Memory filtering component.

Filters memories before storage based on quality and relevance criteria.
"""

import re
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


class MemoryFilter:
    """
    Filter memories before storage based on quality and relevance criteria.
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
                return False, 'Non-essential system message'

            # Check for duplicates
            if self._is_duplicate(content):
                return False, 'Duplicate content within time window'

            # Tool responses with errors might not be worth storing
            if metadata and metadata.get('tool_name'):
                if metadata.get('error') and not self._is_important_error(metadata):
                    return False, 'Non-critical tool error'

            # Content appears to be worth storing
            return True, 'Passes all filters'

        except Exception as e:
            logger.error(f'Error in memory filter: {e}')
            # Default to storing on error
            return True, 'Filter error - defaulting to store'

    def _is_important_system_message(self, content: str) -> bool:
        """Check if a system message is important enough to store."""
        important_keywords = [
            'initialized',
            'configured',
            'started',
            'stopped',
            'error',
            'warning',
            'critical',
            'failed',
        ]

        content_lower = content.lower()
        return any(keyword in content_lower for keyword in important_keywords)

    def _is_duplicate(self, content: str) -> bool:
        """Check if content is a duplicate of recent messages."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=self.duplicate_window)

        # Clean old messages from cache
        self.recent_messages = [
            (msg, timestamp)
            for msg, timestamp in self.recent_messages
            if timestamp > cutoff_time
        ]

        # Check for duplicate
        content_normalized = content.strip().lower()
        for cached_content, _ in self.recent_messages:
            if cached_content.strip().lower() == content_normalized:
                return True

        # Add to cache
        self.recent_messages.append((content, current_time))
        return False

    def _is_important_error(self, metadata: dict[str, Any]) -> bool:
        """Check if an error is important enough to store."""
        # Certain tools' errors might be more critical
        critical_tools = ['web_search', 'arxiv_search', 'pdf_download']
        tool_name = metadata.get('tool_name', '').lower()

        if any(critical in tool_name for critical in critical_tools):
            return True

        # Check error severity
        error_msg = str(metadata.get('error', '')).lower()
        critical_terms = ['failed', 'unauthorized', 'forbidden', 'timeout', 'critical']

        return any(term in error_msg for term in critical_terms)