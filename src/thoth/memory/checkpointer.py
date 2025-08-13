"""
LangGraph Checkpointer for Thoth Memory Store

This module provides LettaCheckpointer, which implements LangGraph's BaseSaver
interface to bridge Letta's memory system with LangGraph's checkpoint mechanism.
"""

import json
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
)
from loguru import logger

from .store import ThothMemoryStore


class LettaCheckpointer(BaseCheckpointSaver):
    """
    LangGraph checkpointer that uses ThothMemoryStore for persistence.

    This class implements LangGraph's BaseSaver interface to provide
    checkpoint functionality backed by Letta's advanced memory system.
    """

    def __init__(self, store: ThothMemoryStore):
        """
        Initialize the LettaCheckpointer.

        Args:
            store: ThothMemoryStore instance for persistence
        """
        self.store = store
        logger.info('LettaCheckpointer initialized with ThothMemoryStore')

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        """
        Save a checkpoint to the memory store.

        Args:
            config: Runnable configuration
            checkpoint: Checkpoint data to save
            metadata: Checkpoint metadata

        Returns:
            Updated configuration with checkpoint ID
        """
        try:
            # Extract thread/session ID from config
            thread_id = config.get('configurable', {}).get('thread_id', 'default')

            # Generate checkpoint ID if not present
            checkpoint_id = config.get('configurable', {}).get('checkpoint_id')
            if not checkpoint_id:
                checkpoint_id = str(uuid.uuid4())

            # Prepare checkpoint data for storage
            checkpoint_data = {
                'checkpoint': checkpoint,
                'metadata': metadata,
                'config': config,
            }

            # Store checkpoint in memory store using episodic scope for persistence
            memory_id = self.store.write_memory(
                user_id=thread_id,
                content=json.dumps(checkpoint_data, default=str),
                role='system',
                scope='episodic',
                agent_id='langgraph_checkpointer',
                metadata={
                    'type': 'checkpoint',
                    'checkpoint_id': checkpoint_id,
                    'thread_id': thread_id,
                },
                salience_score=1.0,  # High salience for checkpoints
            )

            # Update config with checkpoint information
            updated_config = config.copy()
            if 'configurable' not in updated_config:
                updated_config['configurable'] = {}
            updated_config['configurable']['checkpoint_id'] = checkpoint_id
            updated_config['configurable']['memory_id'] = memory_id

            logger.debug(f'Saved checkpoint {checkpoint_id} for thread {thread_id}')
            return updated_config

        except Exception as e:
            logger.error(f'Failed to save checkpoint: {e}')
            # Return original config on failure
            return config

    def get(self, config: RunnableConfig) -> Checkpoint | None:
        """
        Retrieve a checkpoint from the memory store.

        Args:
            config: Runnable configuration with checkpoint information

        Returns:
            Checkpoint data if found, None otherwise
        """
        try:
            # Extract identifiers from config
            configurable = config.get('configurable', {})
            thread_id = configurable.get('thread_id', 'default')
            checkpoint_id = configurable.get('checkpoint_id')

            if not checkpoint_id:
                logger.debug('No checkpoint ID in config')
                return None

            # Search for checkpoint in episodic memory
            memories = self.store.read_memories(
                user_id=thread_id,
                scope='episodic',
                limit=100,  # Search recent checkpoints
            )

            # Find matching checkpoint
            for memory in memories:
                metadata = memory.get('metadata', {})
                if (
                    metadata.get('type') == 'checkpoint'
                    and metadata.get('checkpoint_id') == checkpoint_id
                ):
                    # Parse checkpoint data
                    content = memory.get('content', '{}')
                    checkpoint_data = json.loads(content)

                    logger.debug(
                        f'Retrieved checkpoint {checkpoint_id} for thread {thread_id}'
                    )
                    return checkpoint_data.get('checkpoint')

            logger.debug(f'Checkpoint {checkpoint_id} not found for thread {thread_id}')
            return None

        except Exception as e:
            logger.error(f'Failed to retrieve checkpoint: {e}')
            return None

    def list(
        self,
        config: RunnableConfig,
        *,
        filter: dict[str, Any] | None = None,  # noqa: ARG002
        before: RunnableConfig | None = None,  # noqa: ARG002
        limit: int | None = None,
    ) -> list[tuple[RunnableConfig, CheckpointMetadata]]:
        """
        List checkpoints for a thread.

        Args:
            config: Runnable configuration
            filter: Filter criteria (not implemented)
            before: Get checkpoints before this config (not implemented)
            limit: Maximum number of checkpoints to return

        Returns:
            List of (config, metadata) tuples
        """
        try:
            # Extract thread ID
            thread_id = config.get('configurable', {}).get('thread_id', 'default')

            # Get all checkpoint memories for this thread
            memories = self.store.read_memories(
                user_id=thread_id, scope='episodic', limit=limit or 50
            )

            # Filter for checkpoint memories
            checkpoint_memories = [
                memory
                for memory in memories
                if memory.get('metadata', {}).get('type') == 'checkpoint'
            ]

            results = []
            for memory in checkpoint_memories:
                try:
                    # Parse checkpoint data
                    content = memory.get('content', '{}')
                    checkpoint_data = json.loads(content)

                    # Extract original config and metadata
                    original_config = checkpoint_data.get('config', {})
                    checkpoint_metadata = checkpoint_data.get('metadata', {})

                    results.append((original_config, checkpoint_metadata))

                except Exception as e:
                    logger.warning(f'Failed to parse checkpoint memory: {e}')

            logger.debug(f'Listed {len(results)} checkpoints for thread {thread_id}')
            return results

        except Exception as e:
            logger.error(f'Failed to list checkpoints: {e}')
            return []

    def exists(self, config: RunnableConfig) -> bool:
        """
        Check if a checkpoint exists.

        Args:
            config: Runnable configuration with checkpoint information

        Returns:
            True if checkpoint exists, False otherwise
        """
        try:
            checkpoint = self.get(config)
            return checkpoint is not None
        except Exception as e:
            logger.error(f'Failed to check checkpoint existence: {e}')
            return False

    def delete(self, config: RunnableConfig) -> None:
        """
        Delete a checkpoint from the memory store.

        Args:
            config: Runnable configuration with checkpoint information
        """
        try:
            # Extract identifiers
            configurable = config.get('configurable', {})
            thread_id = configurable.get('thread_id', 'default')
            checkpoint_id = configurable.get('checkpoint_id')
            memory_id = configurable.get('memory_id')

            if not checkpoint_id:
                logger.debug('No checkpoint ID to delete')
                return

            # If we have the memory ID, delete directly
            if memory_id:
                success = self.store.delete_memory(
                    memory_id=memory_id, user_id=thread_id, scope='episodic'
                )
                if success:
                    logger.debug(
                        f'Deleted checkpoint {checkpoint_id} for thread {thread_id}'
                    )
                return

            # Otherwise, search and delete
            memories = self.store.read_memories(
                user_id=thread_id, scope='episodic', limit=100
            )

            for memory in memories:
                metadata = memory.get('metadata', {})
                if (
                    metadata.get('type') == 'checkpoint'
                    and metadata.get('checkpoint_id') == checkpoint_id
                ):
                    memory_id = memory.get('id')
                    if memory_id:
                        self.store.delete_memory(
                            memory_id=memory_id, user_id=thread_id, scope='episodic'
                        )
                        logger.debug(
                            f'Deleted checkpoint {checkpoint_id} for thread {thread_id}'
                        )
                        break

        except Exception as e:
            logger.error(f'Failed to delete checkpoint: {e}')

    def clear_thread_checkpoints(self, thread_id: str) -> int:
        """
        Clear all checkpoints for a specific thread.

        Args:
            thread_id: Thread identifier

        Returns:
            Number of checkpoints cleared
        """
        try:
            # Get all episodic memories for this thread
            memories = self.store.read_memories(user_id=thread_id, scope='episodic')

            # Filter and delete checkpoint memories
            cleared_count = 0
            for memory in memories:
                metadata = memory.get('metadata', {})
                if metadata.get('type') == 'checkpoint':
                    memory_id = memory.get('id')
                    if memory_id and self.store.delete_memory(
                        memory_id=memory_id, user_id=thread_id, scope='episodic'
                    ):
                        cleared_count += 1

            logger.info(f'Cleared {cleared_count} checkpoints for thread {thread_id}')
            return cleared_count

        except Exception as e:
            logger.error(f'Failed to clear thread checkpoints: {e}')
            return 0

    def get_checkpoint_stats(self, thread_id: str) -> dict[str, Any]:
        """
        Get checkpoint statistics for a thread.

        Args:
            thread_id: Thread identifier

        Returns:
            Dictionary with checkpoint statistics
        """
        try:
            # Get all episodic memories for this thread
            memories = self.store.read_memories(user_id=thread_id, scope='episodic')

            # Filter checkpoint memories
            checkpoint_memories = [
                memory
                for memory in memories
                if memory.get('metadata', {}).get('type') == 'checkpoint'
            ]

            return {
                'thread_id': thread_id,
                'total_checkpoints': len(checkpoint_memories),
                'latest_checkpoint': checkpoint_memories[0]
                if checkpoint_memories
                else None,
                'oldest_checkpoint': checkpoint_memories[-1]
                if checkpoint_memories
                else None,
            }

        except Exception as e:
            logger.error(f'Failed to get checkpoint stats: {e}')
            return {'error': str(e)}

    def health_check(self) -> dict[str, Any]:
        """
        Check the health of the checkpointer.

        Returns:
            Dictionary with health status
        """
        try:
            # Test the underlying memory store
            store_health = self.store.health_check()

            # Test basic checkpoint operations
            test_config = {
                'configurable': {
                    'thread_id': 'health_check',
                    'checkpoint_id': 'test_checkpoint',
                }
            }

            test_checkpoint = {'test': True, 'data': 'health_check'}
            test_metadata = {'source': 'health_check'}

            # Test put operation
            try:
                updated_config = self.put(test_config, test_checkpoint, test_metadata)
                put_test = 'pass'
            except Exception as e:
                put_test = f'fail: {e}'

            # Test get operation
            try:
                retrieved = (
                    self.get(updated_config) if 'updated_config' in locals() else None
                )
                get_test = 'pass' if retrieved else 'fail'
            except Exception as e:
                get_test = f'fail: {e}'

            # Cleanup
            try:
                if 'updated_config' in locals():
                    self.delete(updated_config)
            except Exception:
                pass  # Ignore cleanup errors

            return {
                'status': 'healthy'
                if store_health.get('status') == 'healthy'
                else 'unhealthy',
                'store_health': store_health,
                'put_test': put_test,
                'get_test': get_test,
                'component': 'LettaCheckpointer',
            }

        except Exception as e:
            logger.error(f'Checkpointer health check failed: {e}')
            return {
                'status': 'unhealthy',
                'error': str(e),
                'component': 'LettaCheckpointer',
            }
