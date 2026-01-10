"""
Letta Filesystem Service for syncing Obsidian vault files to Letta.

This service manages the synchronization of vault files to Letta's filesystem,
enabling agents to access vault content via Letta's native file tools
(open_file, grep_file, search_file).
"""

import asyncio
from pathlib import Path
from typing import Any

from letta import LettaClient
from loguru import logger

from thoth.services.base import BaseService, ServiceError


class LettaFilesystemService(BaseService):
    """
    Service for syncing vault files to Letta filesystem.

    This service handles:
    - Creating Letta folders with proper embedding configuration
    - Uploading vault files to Letta via API
    - Tracking sync state and detecting changes
    - Attaching folders to agents
    """

    def __init__(self, config=None):
        """
        Initialize the Letta Filesystem Service.

        Args:
            config: Optional configuration object
        """
        super().__init__(config)
        self._client: LettaClient | None = None
        self._folder_id: str | None = None
        self._sync_state: dict[str, dict[str, Any]] = {}  # file_path -> {size, mtime, letta_file_id}

    def initialize(self) -> None:
        """Initialize the Letta filesystem service."""
        try:
            # Initialize Letta client
            base_url = self.config.memory.letta.server_url
            api_key = None  # For self-hosted without auth
            
            self.logger.info(f'Initializing Letta client with base_url: {base_url}')
            
            self._client = LettaClient(
                base_url=base_url,
                token=api_key
            )
            
            self.logger.info('Letta Filesystem Service initialized')
        except Exception as e:
            self.logger.error(f'Failed to initialize Letta client: {e}')
            raise ServiceError(f'Letta client initialization failed: {e}')

    @property
    def client(self) -> LettaClient:
        """Get the Letta client instance."""
        if self._client is None:
            self.initialize()
        return self._client

    async def create_folder(
        self,
        name: str,
        embedding_model: str = 'openai/text-embedding-3-small'
    ) -> str:
        """
        Create a Letta folder for storing vault files.

        Args:
            name: Folder name (e.g., 'thoth_processed_articles')
            embedding_model: Embedding model to use (must match RAG config)

        Returns:
            Folder ID

        Raises:
            ServiceError: If folder creation fails
        """
        try:
            self.logger.info(f'Creating Letta folder: {name} with embedding: {embedding_model}')
            
            # Create folder via Letta API
            folder = await asyncio.to_thread(
                self.client.folders.create,
                name=name,
                embedding=embedding_model
            )
            
            folder_id = folder.id
            self._folder_id = folder_id
            
            self.logger.info(f'Created Letta folder: {folder_id}')
            return folder_id
            
        except Exception as e:
            self.logger.error(f'Failed to create Letta folder: {e}')
            raise ServiceError(f'Folder creation failed: {e}')

    async def get_or_create_folder(
        self,
        name: str,
        embedding_model: str = 'openai/text-embedding-3-small'
    ) -> str:
        """
        Get existing folder or create if doesn't exist.

        Args:
            name: Folder name
            embedding_model: Embedding model to use

        Returns:
            Folder ID
        """
        try:
            # List existing folders
            folders = await asyncio.to_thread(self.client.folders.list)
            
            # Check if folder with this name exists
            for folder in folders:
                if folder.name == name:
                    self.logger.info(f'Found existing Letta folder: {folder.id}')
                    self._folder_id = folder.id
                    return folder.id
            
            # Folder doesn't exist, create it
            return await self.create_folder(name, embedding_model)
            
        except Exception as e:
            self.logger.error(f'Failed to get or create folder: {e}')
            raise ServiceError(f'Folder retrieval/creation failed: {e}')

    async def upload_file(
        self,
        folder_id: str,
        file_path: Path
    ) -> dict[str, Any]:
        """
        Upload a single file to Letta folder.

        Args:
            folder_id: Letta folder ID
            file_path: Path to local file

        Returns:
            Dict with upload status and job info

        Raises:
            ServiceError: If upload fails
        """
        try:
            if not file_path.exists():
                raise ServiceError(f'File does not exist: {file_path}')
            
            self.logger.info(f'Uploading file to Letta: {file_path.name}')
            
            # Upload file and get job
            with open(file_path, 'rb') as f:
                job = await asyncio.to_thread(
                    self.client.folders.files.upload,
                    f,
                    folder_id
                )
            
            # Wait for processing job to complete
            max_wait = 300  # 5 minutes
            elapsed = 0
            while elapsed < max_wait:
                job_status = await asyncio.to_thread(
                    self.client.jobs.retrieve,
                    job.id
                )
                
                if job_status.status == 'completed':
                    self.logger.info(f'File uploaded successfully: {file_path.name}')
                    
                    # Update sync state
                    stat = file_path.stat()
                    self._sync_state[str(file_path)] = {
                        'size': stat.st_size,
                        'mtime': stat.st_mtime,
                        'letta_file_id': job_status.metadata.get('file_id') if hasattr(job_status, 'metadata') else None
                    }
                    
                    return {
                        'success': True,
                        'file': file_path.name,
                        'job_id': job.id
                    }
                    
                elif job_status.status == 'failed':
                    error_msg = job_status.metadata.get('error', 'Unknown error') if hasattr(job_status, 'metadata') else 'Unknown error'
                    raise ServiceError(f'Upload job failed: {error_msg}')
                
                # Wait before checking again
                await asyncio.sleep(1)
                elapsed += 1
            
            raise ServiceError(f'Upload job timed out after {max_wait}s')
            
        except Exception as e:
            self.logger.error(f'Failed to upload file {file_path.name}: {e}')
            raise ServiceError(f'File upload failed: {e}')

    async def sync_vault_to_folder(
        self,
        folder_id: str,
        notes_dir: Path | None = None
    ) -> dict[str, Any]:
        """
        Sync all vault markdown files to Letta folder.

        Only uploads files that:
        - Are new (not in sync state)
        - Have been modified (size or mtime changed)

        Args:
            folder_id: Letta folder ID
            notes_dir: Directory containing notes (defaults to config.notes_dir)

        Returns:
            Dict with sync statistics
        """
        try:
            notes_path = notes_dir or self.config.notes_dir
            
            if not notes_path.exists():
                raise ServiceError(f'Notes directory does not exist: {notes_path}')
            
            self.logger.info(f'Starting vault sync from: {notes_path}')
            
            # Find all markdown files
            md_files = list(notes_path.glob('**/*.md'))
            
            stats = {
                'total_files': len(md_files),
                'uploaded': 0,
                'skipped': 0,
                'errors': []
            }
            
            for file_path in md_files:
                try:
                    # Check if file needs upload
                    stat = file_path.stat()
                    file_key = str(file_path)
                    
                    if file_key in self._sync_state:
                        cached = self._sync_state[file_key]
                        if cached['size'] == stat.st_size and cached['mtime'] == stat.st_mtime:
                            self.logger.debug(f'Skipping unchanged file: {file_path.name}')
                            stats['skipped'] += 1
                            continue
                    
                    # File is new or changed, upload it
                    await self.upload_file(folder_id, file_path)
                    stats['uploaded'] += 1
                    
                except Exception as e:
                    error_msg = f'Error uploading {file_path.name}: {e}'
                    self.logger.error(error_msg)
                    stats['errors'].append(error_msg)
            
            self.logger.info(
                f'Sync complete: {stats["uploaded"]} uploaded, '
                f'{stats["skipped"]} skipped, {len(stats["errors"])} errors'
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f'Vault sync failed: {e}')
            raise ServiceError(f'Sync failed: {e}')

    async def attach_folder_to_agent(
        self,
        agent_id: str,
        folder_id: str
    ) -> bool:
        """
        Attach a Letta folder to an agent.

        This gives the agent access to all files in the folder
        via file tools (open_file, grep_file, search_file).

        Args:
            agent_id: Letta agent ID
            folder_id: Letta folder ID

        Returns:
            True if successful

        Raises:
            ServiceError: If attachment fails
        """
        try:
            self.logger.info(f'Attaching folder {folder_id} to agent {agent_id}')
            
            await asyncio.to_thread(
                self.client.agents.folders.attach,
                agent_id=agent_id,
                folder_id=folder_id
            )
            
            self.logger.info('Folder attached successfully')
            return True
            
        except Exception as e:
            self.logger.error(f'Failed to attach folder to agent: {e}')
            raise ServiceError(f'Folder attachment failed: {e}')

    def get_sync_stats(self) -> dict[str, Any]:
        """
        Get current sync state statistics.

        Returns:
            Dict with sync state info
        """
        return {
            'tracked_files': len(self._sync_state),
            'folder_id': self._folder_id,
            'sync_state_keys': list(self._sync_state.keys())
        }
