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
from letta_client import Letta

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
        self._letta_client: Letta | None = None

    def initialize(self) -> None:
        """Initialize the Letta filesystem service."""
        try:
            letta_config = self.config.memory_config.letta if hasattr(self.config.memory_config, 'letta') else {}
            mode = getattr(letta_config, 'mode', 'self-hosted')
            
            # Override with environment variable if set
            mode = os.getenv('LETTA_MODE', mode)
            
            if mode == 'cloud':
                # Letta Cloud mode
                self.logger.info('Initializing Letta client in cloud mode')
                oauth_enabled = getattr(letta_config, 'oauth_enabled', True)
                cloud_api_key = os.getenv('LETTA_CLOUD_API_KEY') or getattr(letta_config, 'cloud_api_key', '')
                
                if oauth_enabled and not cloud_api_key:
                    # Use OAuth credentials from ~/.letta/credentials
                    credentials_path = os.getenv('LETTA_CREDENTIALS_PATH') or getattr(
                        letta_config, 'oauth_credentials_path', '~/.letta/credentials'
                    )
                    credentials_path = os.path.expanduser(credentials_path)
                    
                    if not os.path.exists(credentials_path):
                        raise ServiceError(
                            'Letta Cloud OAuth credentials not found. '
                            'Run "thoth letta auth login" to authenticate, '
                            'or set LETTA_CLOUD_API_KEY environment variable.'
                        )
                    
                    self.logger.info(f'Using Letta Cloud with OAuth credentials from {credentials_path}')
                    self._letta_client = Letta()  # Auto-loads from ~/.letta/credentials
                    self._base_url = 'https://api.letta.com/'
                    self._token = None  # OAuth handles authentication
                
                elif cloud_api_key:
                    # Use explicit API key
                    self.logger.info('Using Letta Cloud with API key')
                    self._letta_client = Letta(token=cloud_api_key)
                    self._base_url = 'https://api.letta.com/'
                    self._token = cloud_api_key
                
                else:
                    raise ServiceError(
                        'Letta Cloud mode requires either OAuth credentials or API key. '
                        'Run "thoth letta auth login" or set LETTA_CLOUD_API_KEY'
                    )
            
            else:
                # Self-hosted mode (existing logic)
                self.logger.info('Initializing Letta client in self-hosted mode')
                server_url = getattr(letta_config, 'server_url', 'http://localhost:8283')
                
                # Override with environment variable if set
                server_url = os.getenv('LETTA_SERVER_URL', server_url)
                
                # If in Docker, replace localhost with service name
                if os.getenv('DOCKER_ENV') or os.getenv('THOTH_DOCKER'):
                    server_url = server_url.replace('localhost', 'letta-server')

                # Ensure trailing slash to avoid 307 redirects
                if not server_url.endswith('/'):
                    server_url = server_url + '/'

                self._base_url = server_url
                self._token = os.getenv('LETTA_API_KEY') or os.getenv('LETTA_SERVER_PASSWORD', 'letta_dev_password')
                
                self.logger.info(f'Using self-hosted Letta at: {self._base_url}')
                self._letta_client = Letta(base_url=self._base_url, token=self._token)
            
            # Test connection
            try:
                response = requests.get(
                    f'{self._base_url}v1/health/',
                    headers=self._get_headers() if self._token else {},
                    allow_redirects=True,
                    timeout=10
                )
                if response.status_code == 200:
                    self.logger.info(f'Letta connection successful ({mode} mode)')
                else:
                    self.logger.warning(f'Letta health check returned {response.status_code}')
            except Exception as health_error:
                self.logger.warning(f'Could not verify Letta connection: {health_error}')
                # Don't fail initialization - health check might not be available
                
        except Exception as e:
            self.logger.error(f'Failed to initialize Letta client: {e}')
            raise ServiceError(f'Letta client initialization failed: {e}')
    
    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for Letta API requests."""
        headers = {'Content-Type': 'application/json'}
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        return headers

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized."""
        if self._base_url is None:
            self.initialize()

    async def create_folder(
        self,
        name: str,
        embedding_model: str = 'text-embedding-3-small'
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
            
            # Create folder via Letta client
            from letta_client.types import EmbeddingConfig
            embedding_config = EmbeddingConfig(
                embedding_model=embedding_model,
                embedding_endpoint_type='openai',  # For openai/text-embedding-*
                embedding_dim=1536  # Dimension for text-embedding-3-small
            )
            
            folder = await asyncio.to_thread(
                self._letta_client.folders.create,
                name=name,
                embedding_config=embedding_config
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
        embedding_model: str = 'text-embedding-3-small'
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
            # List existing folders via Letta client
            folders = await asyncio.to_thread(
                self._letta_client.folders.list
            )
            
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
        self._ensure_initialized()
        try:
            if not file_path.exists():
                raise ServiceError(f'File does not exist: {file_path}')
            
            self.logger.info(f'Uploading file to Letta: {file_path.name}')
            
            # Upload file via Letta client
            with open(file_path, 'rb') as f:
                result = await asyncio.to_thread(
                    self._letta_client.folders.files.upload,
                    folder_id,
                    file=f
                )
            
            # result is FileMetadata object
            job_id = result.job_id if hasattr(result, 'job_id') else None
            if not job_id:
                # File might have been processed immediately
                self.logger.info(f'File uploaded successfully (no async job): {file_path.name}')
                stat = file_path.stat()
                self._sync_state[str(file_path)] = {
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'letta_file_id': result.id if hasattr(result, 'id') else None
                }
                return {
                    'success': True,
                    'file': file_path.name,
                    'file_id': result.id if hasattr(result, 'id') else None
                }
            
            # If job_id exists, wait for processing job to complete
            if job_id:
                max_wait = 300  # 5 minutes
                elapsed = 0
                while elapsed < max_wait:
                    try:
                        job_status = await asyncio.to_thread(
                            self._letta_client.jobs.retrieve,
                            job_id
                        )
                        
                        if job_status.status == 'completed':
                            self.logger.info(f'File uploaded successfully: {file_path.name}')
                            
                            # Update sync state
                            stat = file_path.stat()
                            self._sync_state[str(file_path)] = {
                                'size': stat.st_size,
                                'mtime': stat.st_mtime,
                                'letta_file_id': result.id if hasattr(result, 'id') else None
                            }
                            
                            return {
                                'success': True,
                                'file': file_path.name,
                                'job_id': job_id
                            }
                            
                        elif job_status.status == 'failed':
                            error_msg = getattr(job_status, 'error', 'Unknown error')
                            raise ServiceError(f'Upload job failed: {error_msg}')
                        
                    except Exception as e:
                        # Job might not exist yet
                        self.logger.debug(f'Waiting for job {job_id}: {e}')
                    
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
            
            # Find all PDF and markdown files
            pdf_files = list(notes_path.glob('**/*.pdf'))
            md_files = list(notes_path.glob('**/*.md'))
            all_files = pdf_files + md_files
            
            stats = {
                'total_files': len(all_files),
                'pdfs': len(pdf_files),
                'markdown': len(md_files),
                'uploaded': 0,
                'skipped': 0,
                'errors': []
            }
            
            self.logger.info(f'Found {len(pdf_files)} PDFs and {len(md_files)} markdown files')
            
            for file_path in all_files:
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
            
            # Use agents.folders.attach method
            await asyncio.to_thread(
                self._letta_client.agents.folders.attach,
                agent_id,
                folder_id
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
