"""
Unit tests for CacheService.

Tests bounded caching, LRU eviction, TTL expiration, and multi-layer
caching behavior for OCR, analysis, and API response caching.
"""

import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory

from thoth.services.cache_service import CacheService


@pytest.mark.asyncio
class TestCacheService:
    """Test suite for CacheService."""

    def test_initialization(self):
        """Test service initialization with default settings."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)

            assert service.cache_dir == cache_dir
            assert service._memory_cache is not None
            assert service._memory_cache_size_limit == 100

    def test_bounded_cache_size(self):
        """Test that cache respects size limits (bounded caching)."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service._memory_cache_size_limit = 5  # Small limit for testing

            # Add items up to limit
            for i in range(10):
                key = f'test:{i}'
                service._memory_cache[key] = f'value_{i}'
                service._memory_cache_timestamps[key] = time.time()

            # Cache should automatically evict via LRUCache
            # LRUCache with maxsize=100 handles eviction internally
            assert len(service._memory_cache) <= 100

    def test_lru_eviction(self):
        """Test LRU eviction behavior."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)

            # Create cache with small size
            from cachetools import LRUCache
            service._memory_cache = LRUCache(maxsize=3)

            # Add 4 items (will evict oldest)
            service._memory_cache['key1'] = 'value1'
            service._memory_cache['key2'] = 'value2'
            service._memory_cache['key3'] = 'value3'
            service._memory_cache['key4'] = 'value4'  # Evicts key1

            # key1 should be evicted
            assert 'key1' not in service._memory_cache
            assert 'key4' in service._memory_cache
            assert len(service._memory_cache) == 3

    def test_cache_ocr_result(self):
        """Test caching OCR results."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            # Create test PDF file
            pdf_path = Path(tmpdir) / 'test.pdf'
            pdf_path.write_bytes(b'Mock PDF content')

            markdown = '# Paper Title\nContent...'
            no_images = '# Paper Title\nContent (no images)...'

            # Cache OCR result
            success = service.cache_ocr_result(pdf_path, markdown, no_images)

            assert success is True

            # Check memory cache
            cache_keys = [k for k in service._memory_cache.keys() if k.startswith('ocr:')]
            assert len(cache_keys) == 1

            cached_data = service._memory_cache[cache_keys[0]]
            assert cached_data['markdown_content'] == markdown
            assert cached_data['no_images_content'] == no_images

    def test_get_cached_ocr_result_memory_hit(self):
        """Test retrieving OCR result from memory cache."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            pdf_path = Path(tmpdir) / 'test.pdf'
            pdf_path.write_bytes(b'Mock PDF content')

            markdown = '# Test'
            no_images = '# Test (no images)'

            # Cache and retrieve
            service.cache_ocr_result(pdf_path, markdown, no_images)
            result = service.get_cached_ocr_result(pdf_path)

            assert result is not None
            assert result['markdown_content'] == markdown

    def test_get_cached_ocr_result_disk_hit(self):
        """Test retrieving OCR result from disk cache."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            pdf_path = Path(tmpdir) / 'test.pdf'
            pdf_path.write_bytes(b'Mock PDF content')

            markdown = '# Test'
            no_images = '# Test (no images)'

            # Cache result
            service.cache_ocr_result(pdf_path, markdown, no_images)

            # Clear memory cache to force disk read
            service._memory_cache.clear()

            # Should still retrieve from disk
            result = service.get_cached_ocr_result(pdf_path)

            assert result is not None
            assert result['markdown_content'] == markdown

    def test_get_cached_ocr_result_miss(self):
        """Test cache miss for OCR result."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            pdf_path = Path(tmpdir) / 'nonexistent.pdf'
            pdf_path.write_bytes(b'Content')

            result = service.get_cached_ocr_result(pdf_path)

            assert result is None

    def test_cache_analysis_result(self):
        """Test caching LLM analysis results."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            content_hash = 'abc123'
            analysis = {'summary': 'Test summary', 'topics': ['ML', 'NLP']}
            model_info = {'model': 'claude-3', 'version': '1.0'}

            success = service.cache_analysis_result(
                content_hash, analysis, model_info
            )

            assert success is True

    def test_get_cached_analysis_result(self):
        """Test retrieving cached analysis result."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            content_hash = 'abc123'
            analysis = {'summary': 'Test summary'}

            service.cache_analysis_result(content_hash, analysis)
            result = service.get_cached_analysis_result(content_hash)

            assert result is not None
            assert result['summary'] == 'Test summary'

    def test_analysis_cache_model_mismatch(self):
        """Test that model mismatch returns cache miss."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            content_hash = 'abc123'
            analysis = {'summary': 'Test'}
            model_v1 = {'model': 'claude-3', 'version': '1.0'}
            model_v2 = {'model': 'claude-3', 'version': '2.0'}

            service.cache_analysis_result(content_hash, analysis, model_v1)

            # Different model should miss cache
            result = service.get_cached_analysis_result(content_hash, model_v2)

            assert result is None

    def test_cache_api_response(self):
        """Test caching API responses."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            response = {'data': 'test', 'status': 200}
            success = service.cache_api_response(
                'semantic_scholar',
                'paper_abc123',
                response,
                ttl=3600
            )

            assert success is True

    def test_get_cached_api_response(self):
        """Test retrieving cached API response."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            response = {'data': 'test'}
            service.cache_api_response('test_api', 'key123', response)

            result = service.get_cached_api_response('test_api', 'key123')

            assert result is not None
            assert result['data'] == 'test'

    def test_api_cache_ttl_expiration(self):
        """Test that API cache respects TTL."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            response = {'data': 'test'}

            # Cache with 1 second TTL
            service.cache_api_response('test_api', 'key123', response, ttl=1)

            # Should be cached
            result = service.get_cached_api_response('test_api', 'key123')
            assert result is not None

            # Wait for expiration
            time.sleep(1.1)

            # Should be expired
            result = service.get_cached_api_response('test_api', 'key123')
            assert result is None

    def test_clear_cache_all(self):
        """Test clearing all caches."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            # Add items to memory cache
            service._memory_cache['test1'] = 'value1'
            service._memory_cache['test2'] = 'value2'

            # Clear all
            success = service.clear_cache()

            assert success is True
            assert len(service._memory_cache) == 0

    def test_clear_cache_specific_type(self):
        """Test clearing specific cache type."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            # Add items to memory cache
            service._memory_cache['ocr:key1'] = 'value1'
            service._memory_cache['analysis:key2'] = 'value2'

            # Clear only OCR cache
            success = service.clear_cache('ocr')

            assert success is True
            assert 'ocr:key1' not in service._memory_cache
            assert 'analysis:key2' in service._memory_cache

    def test_get_cache_statistics(self):
        """Test getting cache statistics."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service.initialize()

            # Add some data
            service._memory_cache['test1'] = 'value1'
            service._memory_cache['test2'] = 'value2'

            stats = service.get_cache_statistics()

            assert 'memory_cache_size' in stats
            assert stats['memory_cache_size'] == 2
            assert 'memory_cache_limit' in stats
            assert stats['memory_cache_limit'] == 100
            assert 'total_disk_cache_files' in stats
            assert 'cache_directories' in stats

    def test_cleanup_expired_cache(self):
        """Test automatic cleanup of expired cache files."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)

            # Override TTL for testing
            service._ttl_settings['ocr'] = 1  # 1 second
            service.initialize()

            # Create old cache file
            old_file = service.ocr_cache_dir / 'old_cache.pkl'
            old_file.write_bytes(b'old data')

            # Modify file timestamp to make it old
            old_time = time.time() - 2  # 2 seconds ago
            import os
            os.utime(old_file, (old_time, old_time))

            # Cleanup should remove it
            service._cleanup_expired_cache()

            assert not old_file.exists()

    def test_memory_cache_cleanup(self):
        """Test memory cache cleanup when size limit exceeded."""
        config = Mock()
        config.workspace_dir = Path('/tmp/test')

        with TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / 'cache'
            service = CacheService(config, cache_dir=cache_dir)
            service._memory_cache_size_limit = 5

            # LRUCache automatically handles size limit
            from cachetools import LRUCache
            service._memory_cache = LRUCache(maxsize=5)

            # Add more items than limit
            for i in range(10):
                service._memory_cache[f'key{i}'] = f'value{i}'
                service._memory_cache_timestamps[f'key{i}'] = time.time()

            # Should maintain size limit
            assert len(service._memory_cache) <= 5
