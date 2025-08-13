"""
Thoth Memory Management System

This package integrates Letta's advanced memory capabilities with Thoth's
research assistant agents, providing persistent, intelligent memory management
for research conversations and discoveries.
"""

from .store import ThothMemoryStore

# Shared store singleton for easy import
shared_store: ThothMemoryStore | None = None


def get_shared_store() -> ThothMemoryStore:
    """Get or create the shared memory store instance."""
    global shared_store
    if shared_store is None:
        shared_store = ThothMemoryStore()
    return shared_store


__all__ = ['ThothMemoryStore', 'get_shared_store', 'shared_store']
