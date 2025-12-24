"""
Agent coordination utilities for multi-agent workflows.
Provides message queue functionality via shared memory blocks.
"""

from .message_queue import (
    post_message,
    read_messages,
    read_messages_for_agent,
    mark_message_complete,
    clear_old_messages
)

__all__ = [
    'post_message',
    'read_messages',
    'read_messages_for_agent',
    'mark_message_complete',
    'clear_old_messages'
]
