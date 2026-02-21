"""
Multi-layer caching service for Thoth processing optimization.

This module provides intelligent caching for:
- OCR results
- LLM analysis results
- Citation enhancement data
- API responses
- Embeddings
"""

import hashlib
import json
import pickle  # nosec B403
import time
from pathlib import Path
from typing import Any

from thoth.services.base import BaseService, ServiceError


class CacheService(BaseService):
    """
    Multi-layer caching service for improved performance.

    Provides:
    - Memory cache for frequently accessed data
    - Disk cache for persistent storage
    - TTL-based cache invalidation
    - Cache statistics and management
    """

    def __init__(self, config=None, cache_dir: Path | None = None):
        """
        Initialize the CacheService.

        Args:
            config: Optional configuration object
            cache_dir: Optional cache directory (defaults to config.workspace_dir/cache)
        """
        super().__init__(config)

        # Cache directories (defaults, may be overridden by user paths at call-time)
        self._default_cache_dir = cache_dir or (self.config.workspace_dir / 'cache')
        self.ocr_cache_dir = self._default_cache_dir / 'ocr'
        self.analysis_cache_dir = self._default_cache_dir / 'analysis'
        self.citation_cache_dir = self._default_cache_dir / 'citations'
        self.api_cache_dir = self._default_cache_dir / 'api_responses'
        self.embedding_cache_dir = self._default_cache_dir / 'embeddings'

        # Create cache directories
        for cache_path in [
            self._default_cache_dir,
            self.ocr_cache_dir,
            self.analysis_cache_dir,
            self.citation_cache_dir,
            self.api_cache_dir,
            self.embedding_cache_dir,
        ]:
            cache_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache for frequently accessed items with bounded size
        # Using LRUCache to enforce the size limit automatically
        from cachetools import LRUCache

        self._memory_cache: LRUCache = LRUCache(maxsize=100)
        self._memory_cache_timestamps: dict[str, float] = {}

        # Cache configuration
        self._memory_cache_size_limit = 100  # Max items in memory
        self._default_ttl = 3600 * 24  # 24 hours default TTL

        # Cache TTL settings by type
        self._ttl_settings = {
            'ocr': 3600 * 24 * 7,  # 7 days - OCR rarely changes
            'analysis': 3600
            * 24
            * 3,  # 3 days - Analysis may change with model updates
            'citations': 3600 * 24 * 7,  # 7 days - Citation data is relatively stable
            'api_responses': 3600 * 6,  # 6 hours - API data may update
            'embeddings': 3600
            * 24
            * 7,  # 7 days - Embeddings stable unless model changes
        }

    @property
    def cache_dir(self) -> Path:
        """Cache dir, scoped to current user when available."""
        up = self._get_user_paths()
        return (up.workspace_dir / 'cache') if up else self._default_cache_dir

    def initialize(self) -> None:
        """Initialize the cache service."""
        self.logger.info(f'Cache service initialized with directory: {self.cache_dir}')
        self._cleanup_expired_cache()

    def _get_cache_key(self, identifier: str, cache_type: str = 'general') -> str:
        """Generate a cache key from identifier."""
        combined = f'{cache_type}:{identifier}'
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file content."""
        hasher = hashlib.md5(usedforsecurity=False)  # nosec B324
        with file_path.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _is_cache_valid(self, cache_path: Path, ttl: int) -> bool:
        """Check if cache file is still valid."""
        if not cache_path.exists():
            return False

        file_age = time.time() - cache_path.stat().st_mtime
        return file_age < ttl

    def _cleanup_memory_cache(self):
        """Clean up memory cache if it exceeds size limit."""
        if len(self._memory_cache) <= self._memory_cache_size_limit:
            return

        # Remove oldest entries
        sorted_items = sorted(self._memory_cache_timestamps.items(), key=lambda x: x[1])

        items_to_remove = len(self._memory_cache) - self._memory_cache_size_limit
        for key, _ in sorted_items[:items_to_remove]:
            self._memory_cache.pop(key, None)
            self._memory_cache_timestamps.pop(key, None)

    def cache_ocr_result(
        self, pdf_path: Path, markdown_content: str, no_images_content: str
    ) -> bool:
        """
        Cache OCR results for a PDF.

        Args:
            pdf_path: Path to the PDF file
            markdown_content: Full markdown with images
            no_images_content: Markdown without images

        Returns:
            bool: True if cached successfully
        """
        try:
            pdf_hash = self._get_file_hash(pdf_path)
            cache_key = self._get_cache_key(pdf_hash, 'ocr')

            cache_data = {
                'pdf_path': str(pdf_path),
                'pdf_hash': pdf_hash,
                'markdown_content': markdown_content,
                'no_images_content': no_images_content,
                'timestamp': time.time(),
                'pdf_stem': pdf_path.stem,
            }

            cache_file = self.ocr_cache_dir / f'{cache_key}.pkl'
            with cache_file.open('wb') as f:
                pickle.dump(cache_data, f)

            # Also cache in memory for quick access
            self._memory_cache[f'ocr:{cache_key}'] = cache_data
            self._memory_cache_timestamps[f'ocr:{cache_key}'] = time.time()
            self._cleanup_memory_cache()

            self.logger.debug(f'Cached OCR result for {pdf_path.name}')
            return True

        except Exception as e:
            self.logger.error(f'Failed to cache OCR result: {e}')
            return False

    def get_cached_ocr_result(self, pdf_path: Path) -> dict | None:
        """
        Get cached OCR result for a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            dict | None: Cached OCR data or None if not found/expired
        """
        try:
            pdf_hash = self._get_file_hash(pdf_path)
            cache_key = self._get_cache_key(pdf_hash, 'ocr')

            # Check memory cache first
            memory_key = f'ocr:{cache_key}'
            if memory_key in self._memory_cache:
                cached_data = self._memory_cache[memory_key]
                # Verify hash still matches
                if cached_data['pdf_hash'] == pdf_hash:
                    self.logger.debug(f'OCR cache hit (memory) for {pdf_path.name}')
                    return cached_data
                else:
                    # Hash changed, remove from cache
                    self._memory_cache.pop(memory_key, None)
                    self._memory_cache_timestamps.pop(memory_key, None)

            # Check disk cache
            cache_file = self.ocr_cache_dir / f'{cache_key}.pkl'
            if self._is_cache_valid(cache_file, self._ttl_settings['ocr']):
                with cache_file.open('rb') as f:
                    cached_data = pickle.load(f)  # nosec B301

                # Verify hash still matches
                if cached_data['pdf_hash'] == pdf_hash:
                    # Add to memory cache
                    self._memory_cache[memory_key] = cached_data
                    self._memory_cache_timestamps[memory_key] = time.time()
                    self._cleanup_memory_cache()

                    self.logger.debug(f'OCR cache hit (disk) for {pdf_path.name}')
                    return cached_data
                else:
                    # Hash changed, remove cache file
                    cache_file.unlink(missing_ok=True)

            return None

        except Exception as e:
            self.logger.error(f'Failed to get cached OCR result: {e}')
            return None

    def cache_analysis_result(
        self, content_hash: str, analysis_result: Any, model_info: dict | None = None
    ) -> bool:
        """
        Cache LLM analysis results.

        Args:
            content_hash: Hash of the content that was analyzed
            analysis_result: The analysis result to cache
            model_info: Optional model information for cache validation

        Returns:
            bool: True if cached successfully
        """
        try:
            cache_key = self._get_cache_key(content_hash, 'analysis')

            cache_data = {
                'content_hash': content_hash,
                'analysis_result': analysis_result,
                'model_info': model_info or {},
                'timestamp': time.time(),
            }

            cache_file = self.analysis_cache_dir / f'{cache_key}.pkl'
            with cache_file.open('wb') as f:
                pickle.dump(cache_data, f)

            # Also cache in memory
            memory_key = f'analysis:{cache_key}'
            self._memory_cache[memory_key] = cache_data
            self._memory_cache_timestamps[memory_key] = time.time()
            self._cleanup_memory_cache()

            self.logger.debug(
                f'Cached analysis result for content hash {content_hash[:8]}'
            )
            return True

        except Exception as e:
            self.logger.error(f'Failed to cache analysis result: {e}')
            return False

    def get_cached_analysis_result(
        self, content_hash: str, model_info: dict | None = None
    ) -> Any | None:
        """
        Get cached analysis result.

        Args:
            content_hash: Hash of the content
            model_info: Optional model information for validation

        Returns:
            Analysis result or None if not found/expired
        """
        try:
            cache_key = self._get_cache_key(content_hash, 'analysis')

            # Check memory cache first
            memory_key = f'analysis:{cache_key}'
            if memory_key in self._memory_cache:
                cached_data = self._memory_cache[memory_key]

                # Validate model compatibility if provided
                if model_info and cached_data.get('model_info', {}) != model_info:
                    self.logger.debug('Analysis cache miss: model info mismatch')
                    return None

                self.logger.debug(f'Analysis cache hit (memory) for {content_hash[:8]}')
                return cached_data['analysis_result']

            # Check disk cache
            cache_file = self.analysis_cache_dir / f'{cache_key}.pkl'
            if self._is_cache_valid(cache_file, self._ttl_settings['analysis']):
                with cache_file.open('rb') as f:
                    cached_data = pickle.load(f)  # nosec B301

                # Validate model compatibility
                if model_info and cached_data.get('model_info', {}) != model_info:
                    self.logger.debug('Analysis cache miss: model info mismatch')
                    return None

                # Add to memory cache
                self._memory_cache[memory_key] = cached_data
                self._memory_cache_timestamps[memory_key] = time.time()
                self._cleanup_memory_cache()

                self.logger.debug(f'Analysis cache hit (disk) for {content_hash[:8]}')
                return cached_data['analysis_result']

            return None

        except Exception as e:
            self.logger.error(f'Failed to get cached analysis result: {e}')
            return None

    def cache_api_response(
        self,
        api_name: str,
        request_key: str,
        response_data: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache API response.

        Args:
            api_name: Name of the API (e.g., 'semantic_scholar', 'opencitations')
            request_key: Unique key for the request
            response_data: The response data to cache
            ttl: Optional custom TTL in seconds

        Returns:
            bool: True if cached successfully
        """
        try:
            cache_key = self._get_cache_key(f'{api_name}:{request_key}', 'api')
            ttl = ttl or self._ttl_settings['api_responses']

            cache_data = {
                'api_name': api_name,
                'request_key': request_key,
                'response_data': response_data,
                'timestamp': time.time(),
                'ttl': ttl,
            }

            cache_file = self.api_cache_dir / f'{cache_key}.json'
            with cache_file.open('w') as f:
                json.dump(cache_data, f, default=str)

            # Also cache in memory
            memory_key = f'api:{cache_key}'
            self._memory_cache[memory_key] = cache_data
            self._memory_cache_timestamps[memory_key] = time.time()
            self._cleanup_memory_cache()

            self.logger.debug(f'Cached {api_name} API response for {request_key[:20]}')
            return True

        except Exception as e:
            self.logger.error(f'Failed to cache API response: {e}')
            return False

    def get_cached_api_response(self, api_name: str, request_key: str) -> Any | None:
        """
        Get cached API response.

        Args:
            api_name: Name of the API
            request_key: Unique key for the request

        Returns:
            Response data or None if not found/expired
        """
        try:
            cache_key = self._get_cache_key(f'{api_name}:{request_key}', 'api')

            # Check memory cache first
            memory_key = f'api:{cache_key}'
            if memory_key in self._memory_cache:
                cached_data = self._memory_cache[memory_key]

                # Check custom TTL
                age = time.time() - cached_data['timestamp']
                if age < cached_data.get('ttl', self._ttl_settings['api_responses']):
                    self.logger.debug(
                        f'API cache hit (memory) for {api_name}:{request_key[:20]}'
                    )
                    return cached_data['response_data']
                else:
                    # Expired, remove from memory
                    self._memory_cache.pop(memory_key, None)
                    self._memory_cache_timestamps.pop(memory_key, None)

            # Check disk cache
            cache_file = self.api_cache_dir / f'{cache_key}.json'
            if cache_file.exists():
                with cache_file.open('r') as f:
                    cached_data = json.load(f)

                # Check custom TTL
                age = time.time() - cached_data['timestamp']
                if age < cached_data.get('ttl', self._ttl_settings['api_responses']):
                    # Add to memory cache
                    self._memory_cache[memory_key] = cached_data
                    self._memory_cache_timestamps[memory_key] = time.time()
                    self._cleanup_memory_cache()

                    self.logger.debug(
                        f'API cache hit (disk) for {api_name}:{request_key[:20]}'
                    )
                    return cached_data['response_data']
                else:
                    # Expired, remove cache file
                    cache_file.unlink(missing_ok=True)

            return None

        except Exception as e:
            self.logger.error(f'Failed to get cached API response: {e}')
            return None

    def _cleanup_expired_cache(self):
        """Clean up expired cache files."""
        try:
            current_time = time.time()
            cleaned_count = 0

            for cache_type, cache_dir in [
                ('ocr', self.ocr_cache_dir),
                ('analysis', self.analysis_cache_dir),
                ('citations', self.citation_cache_dir),
                ('api_responses', self.api_cache_dir),
                ('embeddings', self.embedding_cache_dir),
            ]:
                if not cache_dir.exists():
                    continue

                ttl = self._ttl_settings.get(cache_type, self._default_ttl)

                for cache_file in cache_dir.iterdir():
                    if cache_file.is_file():
                        file_age = current_time - cache_file.stat().st_mtime
                        if file_age > ttl:
                            cache_file.unlink(missing_ok=True)
                            cleaned_count += 1

            if cleaned_count > 0:
                self.logger.info(f'Cleaned up {cleaned_count} expired cache files')

        except Exception as e:
            self.logger.error(f'Failed to cleanup expired cache: {e}')

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            stats = {
                'memory_cache_size': len(self._memory_cache),
                'memory_cache_limit': self._memory_cache_size_limit,
                'cache_directories': {},
                'total_disk_cache_files': 0,
                'total_cache_size_mb': 0,
            }

            # Get disk cache statistics
            for cache_type, cache_dir in [
                ('ocr', self.ocr_cache_dir),
                ('analysis', self.analysis_cache_dir),
                ('citations', self.citation_cache_dir),
                ('api_responses', self.api_cache_dir),
                ('embeddings', self.embedding_cache_dir),
            ]:
                if cache_dir.exists():
                    files = list(cache_dir.iterdir())
                    total_size = sum(f.stat().st_size for f in files if f.is_file())

                    stats['cache_directories'][cache_type] = {
                        'files': len(files),
                        'size_mb': round(total_size / (1024 * 1024), 2),
                    }

                    stats['total_disk_cache_files'] += len(files)
                    stats['total_cache_size_mb'] += total_size / (1024 * 1024)

            stats['total_cache_size_mb'] = round(stats['total_cache_size_mb'], 2)

            return stats

        except Exception as e:
            self.logger.error(f'Failed to get cache statistics: {e}')
            return {}

    def clear_cache(self, cache_type: str | None = None) -> bool:
        """
        Clear cache files.

        Args:
            cache_type: Optional specific cache type to clear ('ocr', 'analysis', etc.)
                       If None, clears all caches.

        Returns:
            bool: True if successful
        """
        try:
            cleared_count = 0

            if cache_type is None:
                # Clear all caches
                cache_dirs = [
                    self.ocr_cache_dir,
                    self.analysis_cache_dir,
                    self.citation_cache_dir,
                    self.api_cache_dir,
                    self.embedding_cache_dir,
                ]
                # Clear memory cache
                self._memory_cache.clear()
                self._memory_cache_timestamps.clear()
            else:
                # Clear specific cache
                cache_dir_map = {
                    'ocr': self.ocr_cache_dir,
                    'analysis': self.analysis_cache_dir,
                    'citations': self.citation_cache_dir,
                    'api_responses': self.api_cache_dir,
                    'embeddings': self.embedding_cache_dir,
                }

                if cache_type not in cache_dir_map:
                    raise ServiceError(f'Unknown cache type: {cache_type}')

                cache_dirs = [cache_dir_map[cache_type]]

                # Clear relevant memory cache entries
                memory_keys_to_remove = [
                    key
                    for key in self._memory_cache.keys()
                    if key.startswith(f'{cache_type}:')
                ]
                for key in memory_keys_to_remove:
                    self._memory_cache.pop(key, None)
                    self._memory_cache_timestamps.pop(key, None)

            # Clear disk cache
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    for cache_file in cache_dir.iterdir():
                        if cache_file.is_file():
                            cache_file.unlink(missing_ok=True)
                            cleared_count += 1

            self.logger.info(f'Cleared {cleared_count} cache files')
            return True

        except Exception as e:
            self.logger.error(f'Failed to clear cache: {e}')
            return False

    def health_check(self) -> dict[str, str]:
        """Basic health status for the CacheService."""
        status = super().health_check()
        status['cache_dir_exists'] = str(self.cache_dir.exists())
        status['memory_cache_size'] = str(len(self._memory_cache))
        return status
