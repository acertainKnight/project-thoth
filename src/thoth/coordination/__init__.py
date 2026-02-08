"""
Agent coordination utilities for multi-agent workflows.
Provides message queue functionality via shared memory blocks.
"""

from .message_queue import (
    clear_old_messages,
    mark_message_complete,
    post_message,
    read_messages,
    read_messages_for_agent,
)

__all__ = [
    'clear_old_messages',
    'mark_message_complete',
    'post_message',
    'read_messages',
    'read_messages_for_agent',
]
