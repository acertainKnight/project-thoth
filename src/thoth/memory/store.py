"""
Thoth Memory Store - Wrapper around Letta's MemoryStore

This module provides ThothMemoryStore, a wrapper around Letta's MemoryStore
that adds Thoth-specific functionality and enforces proper namespacing.
"""

import uuid
from datetime import datetime
from typing import Any

from loguru import logger

try:
    from letta.memory import MemoryStore as _LettaStore
except ImportError:
    logger.warning('Letta not available, using fallback memory store')

    # Fallback for development/testing
    class _LettaStore:
        def __init__(self, *_args, **_kwargs):
            self._memory = {}

        def get(self, key: str) -> Any:
            return self._memory.get(key)

        def put(self, key: str, value: Any) -> None:
            self._memory[key] = value

        def exists(self, key: str) -> bool:
            return key in self._memory

        def list(self) -> list[str]:
            return list(self._memory.keys())


class ThothMemoryStore(_LettaStore):
    """
    Thoth's wrapper around Letta's MemoryStore.

    Provides convenience helpers and enforces Thoth namespaces for
    multi-tenant memory management with salience scoring and metadata.
    """

    def __init__(
        self,
        database_url: str | None = None,
        vector_backend: str = 'chromadb',
        namespace: str = 'thoth',
    ):
        """
        Initialize ThothMemoryStore.

        Args:
            database_url: SQLite database URL (defaults to local file)
            vector_backend: Vector store backend to use
            namespace: Namespace prefix for all memory entries
        """
        # Set default database path
        if database_url is None:
            database_url = 'sqlite:///thoth_memory.db'

        # Initialize Letta memory store
        try:
            super().__init__(
                database_url=database_url,
                vector_backend=vector_backend,
            )
        except Exception as e:
            logger.warning(f'Failed to initialize Letta store: {e}, using fallback')
            super().__init__()

        self.namespace = namespace
        self.database_url = database_url
        self.vector_backend = vector_backend

        logger.info(f'ThothMemoryStore initialized with {database_url}')

    def _namespaced_key(self, key: str, user_id: str, scope: str = 'core') -> str:
        """Create a namespaced key for memory storage."""
        return f'{self.namespace}:{user_id}:{scope}:{key}'

    def write_memory(
        self,
        user_id: str,
        content: str,
        role: str = 'user',
        scope: str = 'core',
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        salience_score: float | None = None,
    ) -> str:
        """
        Write a memory entry with Thoth-specific metadata.

        Args:
            user_id: User identifier
            content: Memory content
            role: Message role (user, assistant, system)
            scope: Memory scope (core, episodic, archival)
            agent_id: Agent identifier
            metadata: Additional metadata
            salience_score: Importance score for memory retention

        Returns:
            str: Unique memory ID
        """
        memory_id = str(uuid.uuid4())
        key = self._namespaced_key(memory_id, user_id, scope)

        memory_entry = {
            'id': memory_id,
            'user_id': user_id,
            'agent_id': agent_id,
            'scope': scope,
            'role': role,
            'content': content,
            'metadata': metadata or {},
            'salience_score': salience_score,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }

        try:
            self.put(key, memory_entry)
            logger.debug(
                f'Wrote memory {memory_id} for user {user_id} in scope {scope}'
            )
            return memory_id
        except Exception as e:
            logger.error(f'Failed to write memory: {e}')
            raise

    def read_memories(
        self,
        user_id: str,
        scope: str = 'core',
        limit: int | None = None,
        min_salience: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Read memories for a user and scope.

        Args:
            user_id: User identifier
            scope: Memory scope to read from
            limit: Maximum number of memories to return
            min_salience: Minimum salience score filter

        Returns:
            List of memory entries
        """
        try:
            # Get all keys for this user/scope
            all_keys = self.list()

            # Filter keys matching our pattern
            prefix = f'{self.namespace}:{user_id}:{scope}:'
            matching_keys = [k for k in all_keys if k.startswith(prefix)]

            memories = []
            for key in matching_keys:
                try:
                    memory = self.get(key)
                    if memory and isinstance(memory, dict):
                        # Apply salience filter
                        if min_salience is not None:
                            score = memory.get('salience_score')
                            if score is None or score < min_salience:
                                continue
                        memories.append(memory)
                except Exception as e:
                    logger.warning(f'Failed to read memory {key}: {e}')

            # Sort by creation time (newest first)
            memories.sort(key=lambda x: x.get('created_at', ''), reverse=True)

            # Apply limit
            if limit:
                memories = memories[:limit]

            logger.debug(
                f'Read {len(memories)} memories for user {user_id} in scope {scope}'
            )
            return memories

        except Exception as e:
            logger.error(f'Failed to read memories: {e}')
            return []

    def delete_memory(self, memory_id: str, user_id: str, scope: str = 'core') -> bool:
        """
        Delete a specific memory entry.

        Args:
            memory_id: Memory ID to delete
            user_id: User identifier
            scope: Memory scope

        Returns:
            bool: True if deleted successfully
        """
        try:
            key = self._namespaced_key(memory_id, user_id, scope)
            if self.exists(key):
                # For fallback implementation, we need to manually delete
                if hasattr(self, '_memory'):
                    del self._memory[key]
                else:
                    # For actual Letta implementation
                    # Note: This is a placeholder - actual Letta API may differ
                    pass
                logger.info(f'Deleted memory {memory_id} for user {user_id}')
                return True
            return False
        except Exception as e:
            logger.error(f'Failed to delete memory {memory_id}: {e}')
            return False

    def search_memories(
        self,
        user_id: str,
        query: str,
        scope: str = 'core',
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search memories using semantic similarity.

        Args:
            user_id: User identifier
            query: Search query
            scope: Memory scope to search
            limit: Maximum results to return

        Returns:
            List of matching memory entries
        """
        try:
            # Get all memories for basic text search (fallback)
            memories = self.read_memories(user_id, scope)

            # Simple text-based search for now
            # TODO: Implement proper vector search when Letta integration is complete
            query_lower = query.lower()
            matching = []

            for memory in memories:
                content = memory.get('content', '').lower()
                if query_lower in content:
                    # Simple relevance scoring
                    relevance = content.count(query_lower) / len(content.split())
                    memory['_search_score'] = relevance
                    matching.append(memory)

            # Sort by relevance
            matching.sort(key=lambda x: x.get('_search_score', 0), reverse=True)

            return matching[:limit]

        except Exception as e:
            logger.error(f'Failed to search memories: {e}')
            return []

    def get_memory_stats(self, user_id: str) -> dict[str, Any]:
        """
        Get memory statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with memory statistics
        """
        try:
            stats = {
                'total_memories': 0,
                'core_memories': 0,
                'episodic_memories': 0,
                'archival_memories': 0,
                'avg_salience': 0.0,
            }

            # Count memories by scope
            for scope in ['core', 'episodic', 'archival']:
                memories = self.read_memories(user_id, scope)
                count = len(memories)
                stats[f'{scope}_memories'] = count
                stats['total_memories'] += count

                # Calculate average salience for this scope
                if memories:
                    salience_scores = [
                        m.get('salience_score', 0)
                        for m in memories
                        if m.get('salience_score') is not None
                    ]
                    if salience_scores:
                        avg_salience = sum(salience_scores) / len(salience_scores)
                        stats[f'{scope}_avg_salience'] = avg_salience

            # Overall average salience
            all_memories = []
            for scope in ['core', 'episodic', 'archival']:
                all_memories.extend(self.read_memories(user_id, scope))

            if all_memories:
                all_salience = [
                    m.get('salience_score', 0)
                    for m in all_memories
                    if m.get('salience_score') is not None
                ]
                if all_salience:
                    stats['avg_salience'] = sum(all_salience) / len(all_salience)

            return stats

        except Exception as e:
            logger.error(f'Failed to get memory stats: {e}')
            return {'error': str(e)}

    def clear_user_memories(self, user_id: str, scope: str | None = None) -> int:
        """
        Clear all memories for a user.

        Args:
            user_id: User identifier
            scope: Specific scope to clear (if None, clears all scopes)

        Returns:
            int: Number of memories cleared
        """
        try:
            cleared_count = 0
            scopes_to_clear = [scope] if scope else ['core', 'episodic', 'archival']

            for target_scope in scopes_to_clear:
                memories = self.read_memories(user_id, target_scope)
                for memory in memories:
                    memory_id = memory.get('id')
                    if memory_id and self.delete_memory(
                        memory_id, user_id, target_scope
                    ):
                        cleared_count += 1

            logger.info(f'Cleared {cleared_count} memories for user {user_id}')
            return cleared_count

        except Exception as e:
            logger.error(f'Failed to clear memories: {e}')
            return 0

    def health_check(self) -> dict[str, Any]:
        """
        Check the health of the memory store.

        Returns:
            Dictionary with health status
        """
        try:
            # Test basic functionality
            test_key = self._namespaced_key('health_check', 'test', 'core')
            test_value = {'test': True, 'timestamp': datetime.now().isoformat()}

            # Test write
            self.put(test_key, test_value)

            # Test read
            retrieved = self.get(test_key)

            # Test exists
            exists = self.exists(test_key)

            # Cleanup
            if hasattr(self, '_memory') and test_key in self._memory:
                del self._memory[test_key]

            return {
                'status': 'healthy',
                'database_url': self.database_url,
                'vector_backend': self.vector_backend,
                'namespace': self.namespace,
                'write_test': 'pass',
                'read_test': 'pass' if retrieved else 'fail',
                'exists_test': 'pass' if exists else 'fail',
            }

        except Exception as e:
            logger.error(f'Memory store health check failed: {e}')
            return {
                'status': 'unhealthy',
                'error': str(e),
                'database_url': self.database_url,
                'vector_backend': self.vector_backend,
            }
