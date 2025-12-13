"""
Thoth Memory Management System with Letta Integration

This package integrates Letta's advanced memory capabilities with Thoth's
research assistant agents, providing persistent, intelligent memory management
for research conversations and discoveries.

Key Features:
- Hierarchical memory system (Core/Recall/Archival)
- Self-editing memory tools for agents
- Persistent agent state across sessions
- Semantic memory search and retrieval
"""

from .checkpointer import LettaCheckpointer
from .components import (
    MemoryEnricher,
    MemoryFilter,
    RelevanceScorer,
    RetrievalMetrics,
    RetrievalRanker,
    SalienceScorer,
)
from .letta_integration import LettaMemoryManager
from .pipelines import MemoryRetrievalPipeline, MemoryWritePipeline
from .scheduler import MemoryJobConfig, MemoryScheduler
from .store import ThothMemoryStore
from .summarization import EpisodicSummarizer, MemorySummarizationJob

# Shared instances for easy import
shared_store: ThothMemoryStore | None = None
shared_scheduler: MemoryScheduler | None = None
memory_manager: LettaMemoryManager | None = None


def get_memory_manager() -> LettaMemoryManager:
    """
    Get or create the shared Letta memory manager.

    This is the primary memory system for Thoth, providing:
    - Hierarchical memory (Core/Recall/Archival)
    - Self-editing memory tools
    - Persistent agent state
    - Semantic memory search

    Returns:
        LettaMemoryManager: The shared memory manager instance
    """
    global memory_manager
    if memory_manager is None:
        from thoth.config import config

        # config imported globally from thoth.config

        # Use config values if available
        base_url = getattr(config, 'letta_server_url', 'http://localhost:8283')
        workspace_dir = getattr(config, 'agent_storage_dir', None)
        api_key = (
            getattr(config.api_keys, 'letta_api_key', None)
            if hasattr(config, 'api_keys')
            else None
        )

        memory_manager = LettaMemoryManager(
            base_url=base_url,
            agent_name='thoth_research_agent',
            workspace_dir=workspace_dir,
            api_key=api_key,
        )
    return memory_manager


def get_shared_store() -> ThothMemoryStore:
    """
    Get or create the shared memory store instance.

    This is the legacy memory store, used as fallback when Letta is not available.
    """
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
    'LettaMemoryManager',
    'MemoryEnricher',
    'MemoryFilter',
    'MemoryJobConfig',
    'MemoryRetrievalPipeline',
    'MemoryScheduler',
    'MemorySummarizationJob',
    'MemoryWritePipeline',
    'RelevanceScorer',
    'RetrievalMetrics',
    'RetrievalRanker',
    'SalienceScorer',
    'ThothMemoryStore',
    'get_memory_manager',
    'get_shared_checkpointer',
    'get_shared_scheduler',
    'get_shared_store',
    'memory_manager',
    'shared_scheduler',
    'shared_store',
]
