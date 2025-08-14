"""
Thoth Memory Management System

This package integrates Letta's advanced memory capabilities with Thoth's
research assistant agents, providing persistent, intelligent memory management
for research conversations and discoveries.
"""

from .checkpointer import LettaCheckpointer
from .scheduler import MemoryJobConfig, MemoryScheduler
from .store import ThothMemoryStore
from .summarization import EpisodicSummarizer, MemorySummarizationJob

# Shared instances for easy import
shared_store: ThothMemoryStore | None = None
shared_scheduler: MemoryScheduler | None = None


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


def get_shared_scheduler() -> MemoryScheduler:
    """Get or create the shared memory scheduler instance."""
    global shared_scheduler
    if shared_scheduler is None:
        store = get_shared_store()
        shared_scheduler = MemoryScheduler(store)
        # Initialize default jobs
        shared_scheduler.initialize_default_jobs()
    return shared_scheduler


__all__ = [
    'EpisodicSummarizer',
    'LettaCheckpointer',
    'MemoryJobConfig',
    'MemoryScheduler',
    'MemorySummarizationJob',
    'ThothMemoryStore',
    'get_shared_checkpointer',
    'get_shared_scheduler',
    'get_shared_store',
    'shared_scheduler',
    'shared_store',
]
