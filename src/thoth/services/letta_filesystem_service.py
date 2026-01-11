"""
Letta Filesystem Service for syncing Obsidian vault files to Letta.

This service manages the synchronization of vault files to Letta's filesystem,
enabling agents to access vault content via Letta's native file tools
(open_file, grep_file, search_file).
"""

import asyncio
from pathlib import Path
from typing import Any
import os

import requests
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
        self._base_url: str | None = None
        self._token: str | None = None
        self._folder_id: str | None = None
        self._sync_state: dict[str, dict[str, Any]] = {}  # file_path -> {size, mtime, letta_file_id}

    def initialize(self) -> None:
        """Initialize the Letta filesystem service."""
        try:
            # Initialize Letta REST API connection
            letta_config = self.config.memory_config.letta if hasattr(self.config.memory_config, 'letta') else {}
            self._base_url = getattr(letta_config, 'server_url', 'http://letta-server:8283') if letta_config else 'http://letta-server:8283'
            self._token = os.getenv('LETTA_SERVER_PASSWORD', 'letta_dev_password')
            
            self.logger.info(f'Initializing Letta REST client with base_url: {self._base_url}')
            
            # Test connection
            response = requests.get(
                f'{self._base_url}/v1/health',
                headers=self._get_headers()
            )
            if response.status_code == 200:
                self.logger.info('Letta Filesystem Service initialized successfully')
            else:
                self.logger.warning(f'Letta health check returned {response.status_code}')
        except Exception as e:
            self.logger.error(f'Failed to initialize Letta client: {e}')
            raise ServiceError(f'Letta client initialization failed: {e}')
    
    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for Letta API requests."""
        return {
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/json'
        }

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized."""
        if self._base_url is None:
            self.initialize()

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
        self._ensure_initialized()
        try:
            self.logger.info(f'Creating Letta folder: {name} with embedding: {embedding_model}')
            
            # Create folder via REST API
            response = await asyncio.to_thread(
                requests.post,
                f'{self._base_url}/v1/folders',
                headers=self._get_headers(),
                json={'name': name, 'embedding_config': {'embedding_model': embedding_model}}
            )
            
            if response.status_code not in (200, 201):
                raise ServiceError(f'Failed to create folder: {response.text}')
            
            folder = response.json()
            folder_id = folder['id']
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
        self._ensure_initialized()
        try:
            # List existing folders via REST API
            response = await asyncio.to_thread(
                requests.get,
                f'{self._base_url}/v1/folders',
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                raise ServiceError(f'Failed to list folders: {response.text}')
            
            folders = response.json()
            
            # Check if folder with this name exists
            for folder in folders:
                if folder.get('name') == name:
                    self.logger.info(f'Found existing Letta folder: {folder["id"]}')
                    self._folder_id = folder['id']
                    return folder['id']
            
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
        self._ensure_initialized()
        try:
            if not file_path.exists():
                raise ServiceError(f'File does not exist: {file_path}')
            
            self.logger.info(f'Uploading file to Letta: {file_path.name}')
            
            # Upload file via REST API
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                response = await asyncio.to_thread(
                    requests.post,
                    f'{self._base_url}/v1/folders/{folder_id}/files',
                    headers={'Authorization': f'Bearer {self._token}'},  # Don't include Content-Type, let requests set it
                    files=files
                )
            
            if response.status_code not in (200, 201, 202):
                raise ServiceError(f'Failed to upload file: {response.text}')
            
            result = response.json()
            job_id = result.get('job_id') or result.get('id')
            
            # Wait for processing job to complete
            max_wait = 300  # 5 minutes
            elapsed = 0
            while elapsed < max_wait:
                job_response = await asyncio.to_thread(
                    requests.get,
                    f'{self._base_url}/v1/jobs/{job_id}',
                    headers=self._get_headers()
                )
                
                if job_response.status_code != 200:
                    await asyncio.sleep(2)
                    elapsed += 2
                    continue
                
                job_status = job_response.json()
                
                if job_status.get('status') == 'completed':
                    self.logger.info(f'File uploaded successfully: {file_path.name}')
                    
                    # Update sync state
                    stat = file_path.stat()
                    self._sync_state[str(file_path)] = {
                        'size': stat.st_size,
                        'mtime': stat.st_mtime,
                        'letta_file_id': job_status.get('metadata', {}).get('file_id')
                    }
                    
                    return {
                        'success': True,
                        'file': file_path.name,
                        'job_id': job_id
                    }
                    
                elif job_status.get('status') == 'failed':
                    error_msg = job_status.get('metadata', {}).get('error', 'Unknown error')
                    raise ServiceError(f'Upload job failed: {error_msg}')
                
                # Wait before checking again
                await asyncio.sleep(2)
                elapsed += 2
            
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
        self._ensure_initialized()
        try:
            self.logger.info(f'Attaching folder {folder_id} to agent {agent_id}')
            
            response = await asyncio.to_thread(
                requests.post,
                f'{self._base_url}/v1/agents/{agent_id}/folders/{folder_id}',
                headers=self._get_headers()
            )
            
            if response.status_code not in (200, 201, 204):
                raise ServiceError(f'Failed to attach folder: {response.text}')
            
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
