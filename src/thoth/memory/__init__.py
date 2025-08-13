"""
Thoth Memory Management System

This package integrates Letta's advanced memory capabilities with Thoth's
research assistant agents, providing persistent, intelligent memory management
for research conversations and discoveries.
"""

from .checkpointer import LettaCheckpointer
from .store import ThothMemoryStore

# Shared store singleton for easy import
shared_store: ThothMemoryStore | None = None


def get_shared_store() -> ThothMemoryStore:
    """Get or create the shared memory store instance."""
    global shared_store
    if shared_store is None:
        shared_store = ThothMemoryStore()
    return shared_store


def get_shared_checkpointer() -> LettaCheckpointer:
    """Get or create a checkpointer using the shared memory store."""
    store = get_shared_store()
    return LettaCheckpointer(store)


__all__ = [
    'LettaCheckpointer',
    'ThothMemoryStore',
    'get_shared_checkpointer',
    'get_shared_store',
    'shared_store',
]
