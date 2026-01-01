"""
Unit tests for API clients (CrossRef, OpenAlex, Semantic Scholar).

Tests:
- Mock external API responses
- Rate limiting behavior
- Retry logic on failures
- Cache hit/miss behavior
- Error handling
- Request construction
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import sqlite3
import tempfile
from pathlib import Path

import pytest
import httpx

from thoth.analyze.citations.crossref_resolver import CrossrefResolver, MatchCandidate as CrossrefMatch
from thoth.analyze.citations.openalex_resolver import OpenAlexResolver, MatchCandidate as OpenAlexMatch
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.utilities.schemas.citations import Citation

from tests.fixtures.citation_fixtures import (
    CITATION_WITHOUT_IDENTIFIERS,
    CITATION_MINIMAL,
    MOCK_CROSSREF_RESPONSE,
    MOCK_OPENALEX_RESPONSE,
    MOCK_SEMANTIC_SCHOLAR_PAPER,
)


class TestCrossrefResolverInitialization:
    """Test CrossRef resolver initialization."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        resolver = CrossrefResolver()

        assert resolver.rate_limit == 50
        assert resolver.max_retries == 3
        assert resolver.timeout == 30
        assert resolver.enable_caching is True

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(
                api_key="test_key",
                rate_limit=100,
                max_retries=5,
                timeout=60,
                cache_dir=tmpdir,
                enable_caching=False
            )

            assert resolver.api_key == "test_key"
            assert resolver.rate_limit == 100
            assert resolver.max_retries == 5
            assert resolver.timeout == 60
            assert resolver.enable_caching is False

    def test_cache_initialization(self):
        """Test that cache database is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=True)

            # Check cache database exists
            assert resolver.db_path.exists()

            # Verify table structure
            conn = sqlite3.connect(str(resolver.db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='crossref_cache'"
            )
            assert cursor.fetchone() is not None
            conn.close()


class TestCrossrefResolverCaching:
    """Test CrossRef resolver caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Test cache hit returns cached data without API call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=True)

            # Pre-populate cache
            params = {'query': 'test'}
            cache_key = resolver._generate_cache_key(params)
            resolver._save_to_cache(cache_key, MOCK_CROSSREF_RESPONSE)

            # Mock HTTP client to verify no API call
            with patch.object(resolver, 'client') as mock_client:
                result = await resolver._rate_limited_request(params)

                # Should get cached result without API call
                assert result == MOCK_CROSSREF_RESPONSE
                mock_client.get.assert_not_called()
                assert resolver._stats['cache_hits'] == 1

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss makes API call and caches result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=True)

            params = {'query': 'test'}

            # Mock HTTP client
            mock_response = Mock()
            mock_response.json.return_value = MOCK_CROSSREF_RESPONSE
            mock_response.raise_for_status = Mock()

            with patch.object(resolver, 'client') as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                result = await resolver._rate_limited_request(params)

                # Should make API call
                assert result == MOCK_CROSSREF_RESPONSE
                mock_client.get.assert_called_once()
                assert resolver._stats['cache_misses'] == 1
                assert resolver._stats['api_calls'] == 1

                # Verify result was cached
                cache_key = resolver._generate_cache_key(params)
                cached = resolver._get_from_cache(cache_key)
                assert cached == MOCK_CROSSREF_RESPONSE

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test that caching can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=False)

            params = {'query': 'test'}
            cache_key = resolver._generate_cache_key(params)

            # Try to get from cache (should return None)
            cached = resolver._get_from_cache(cache_key)
            assert cached is None

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=True)

            # Add some cache entries
            for i in range(5):
                params = {'query': f'test{i}'}
                cache_key = resolver._generate_cache_key(params)
                resolver._save_to_cache(cache_key, {'data': i})

            # Clear cache
            deleted = resolver.clear_cache()

            assert deleted == 5

            # Verify cache is empty
            for i in range(5):
                params = {'query': f'test{i}'}
                cache_key = resolver._generate_cache_key(params)
                assert resolver._get_from_cache(cache_key) is None


class TestCrossrefResolverRateLimiting:
    """Test CrossRef resolver rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self):
        """Test that rate limiting delays requests."""
        resolver = CrossrefResolver(rate_limit=10, enable_caching=False)  # 10 req/s

        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        with patch.object(resolver, 'client') as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)

            start = time.time()

            # Make 3 requests
            for i in range(3):
                await resolver._rate_limited_request({'query': f'test{i}'})

            elapsed = time.time() - start

            # Should take at least 0.2 seconds (3 requests at 10 req/s)
            assert elapsed >= 0.2

    @pytest.mark.asyncio
    async def test_rate_limit_429_retry(self):
        """Test retry behavior on 429 rate limit error."""
        resolver = CrossrefResolver(max_retries=2, enable_caching=False)

        # First call returns 429, second succeeds
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        mock_error_response.headers = {'Retry-After': '1'}

        mock_success_response = Mock()
        mock_success_response.json.return_value = MOCK_CROSSREF_RESPONSE
        mock_success_response.raise_for_status = Mock()

        with patch.object(resolver, 'client') as mock_client:
            mock_client.get = AsyncMock(
                side_effect=[
                    httpx.HTTPStatusError(
                        "Too Many Requests",
                        request=Mock(),
                        response=mock_error_response
                    ),
                    mock_success_response
                ]
            )

            with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
                result = await resolver._rate_limited_request({'query': 'test'})

            assert result == MOCK_CROSSREF_RESPONSE
            assert resolver._stats['retries'] == 1


class TestCrossrefResolverRetryLogic:
    """Test CrossRef resolver retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Test exponential backoff retry on server errors."""
        resolver = CrossrefResolver(max_retries=2, enable_caching=False)

        # First call returns 503, second succeeds
        mock_error_response = Mock()
        mock_error_response.status_code = 503

        mock_success_response = Mock()
        mock_success_response.json.return_value = MOCK_CROSSREF_RESPONSE
        mock_success_response.raise_for_status = Mock()

        with patch.object(resolver, 'client') as mock_client:
            mock_client.get = AsyncMock(
                side_effect=[
                    httpx.HTTPStatusError(
                        "Service Unavailable",
                        request=Mock(),
                        response=mock_error_response
                    ),
                    mock_success_response
                ]
            )

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await resolver._rate_limited_request({'query': 'test'})

            assert result == MOCK_CROSSREF_RESPONSE
            assert resolver._stats['retries'] == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self):
        """Test that client errors (4xx) don't retry."""
        resolver = CrossrefResolver(max_retries=2, enable_caching=False)

        mock_error_response = Mock()
        mock_error_response.status_code = 404

        with patch.object(resolver, 'client') as mock_client:
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found",
                    request=Mock(),
                    response=mock_error_response
                )
            )

            result = await resolver._rate_limited_request({'query': 'test'})

            # Should return None without retrying
            assert result is None
            assert mock_client.get.call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test behavior when max retries are exhausted."""
        resolver = CrossrefResolver(max_retries=2, enable_caching=False)

        mock_error_response = Mock()
        mock_error_response.status_code = 503

        with patch.object(resolver, 'client') as mock_client:
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Service Unavailable",
                    request=Mock(),
                    response=mock_error_response
                )
            )

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await resolver._rate_limited_request({'query': 'test'})

            # Should return None after exhausting retries
            assert result is None
            assert mock_client.get.call_count == 3  # Initial + 2 retries


class TestCrossrefResolverQueryConstruction:
    """Test CrossRef query construction."""

    def test_build_query_with_complete_citation(self):
        """Test query construction with complete citation metadata."""
        resolver = CrossrefResolver()

        citation = Citation(
            title="Machine Learning Survey",
            authors=["Smith, J.", "Doe, A."],
            year=2023,
            journal="Nature"
        )

        params = resolver._build_query(citation)

        assert 'query' in params
        assert 'Machine Learning Survey' in params['query']
        assert 'Smith, J.' in params['query']
        assert 'Nature' in params['query']
        assert 'filter' in params
        assert '2022' in params['filter']  # year - 1
        assert '2024' in params['filter']  # year + 1

    def test_build_query_minimal_citation(self):
        """Test query construction with minimal citation."""
        resolver = CrossrefResolver()

        citation = Citation(title="Test Paper")

        params = resolver._build_query(citation)

        assert 'query' in params
        assert 'Test Paper' in params['query']
        assert 'filter' not in params  # No year filter

    def test_build_query_no_title(self):
        """Test query construction fails without title."""
        resolver = CrossrefResolver()

        citation = Citation(authors=["Smith, J."], year=2023)

        params = resolver._build_query(citation)

        # Should return empty query
        assert params.get('query') is None or params['query'] == ''


class TestCrossrefResolverResolution:
    """Test CrossRef citation resolution."""

    @pytest.mark.asyncio
    async def test_resolve_citation_success(self):
        """Test successful citation resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=False)

            with patch.object(
                resolver, '_rate_limited_request', new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = MOCK_CROSSREF_RESPONSE

                matches = await resolver.resolve_citation(CITATION_MINIMAL)

                assert len(matches) > 0
                assert matches[0].doi == "10.1038/nature12345"
                assert matches[0].title == "Deep Learning for Image Recognition"

    @pytest.mark.asyncio
    async def test_resolve_citation_with_doi_skipped(self):
        """Test that citations with DOI are skipped."""
        resolver = CrossrefResolver()

        citation = Citation(
            title="Test",
            doi="10.1234/existing"
        )

        matches = await resolver.resolve_citation(citation)

        # Should return empty list (skipped)
        assert matches == []

    @pytest.mark.asyncio
    async def test_resolve_citation_no_results(self):
        """Test resolution when API returns no results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=False)

            empty_response = {
                'message': {'items': []}
            }

            with patch.object(
                resolver, '_rate_limited_request', new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = empty_response

                matches = await resolver.resolve_citation(CITATION_MINIMAL)

                assert matches == []

    @pytest.mark.asyncio
    async def test_batch_resolve(self):
        """Test batch resolution of multiple citations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = CrossrefResolver(cache_dir=tmpdir, enable_caching=False)

            citations = [CITATION_MINIMAL, CITATION_WITHOUT_IDENTIFIERS]

            with patch.object(
                resolver, '_rate_limited_request', new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = MOCK_CROSSREF_RESPONSE

                results = await resolver.batch_resolve(citations)

                assert len(results) == 2
                for citation in citations:
                    assert citation in results


class TestOpenAlexResolverInitialization:
    """Test OpenAlex resolver initialization."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        resolver = OpenAlexResolver()

        assert resolver.requests_per_second == 10.0
        assert resolver.max_retries == 3
        assert resolver.timeout == 30

    def test_init_with_polite_pool(self):
        """Test initialization with polite pool email."""
        resolver = OpenAlexResolver(email="test@example.com")

        assert resolver.email == "test@example.com"


class TestOpenAlexResolverRateLimiting:
    """Test OpenAlex resolver rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self):
        """Test that rate limiting is enforced."""
        resolver = OpenAlexResolver(requests_per_second=5.0)

        start = time.time()

        # Make 3 requests
        for _ in range(3):
            await resolver._enforce_rate_limit()

        elapsed = time.time() - start

        # Should take at least 0.4 seconds (3 requests at 5 req/s)
        assert elapsed >= 0.4


class TestOpenAlexResolverQueryConstruction:
    """Test OpenAlex query construction."""

    def test_build_search_query(self):
        """Test search query construction."""
        resolver = OpenAlexResolver()

        citation = Citation(
            title="Machine Learning Survey",
            year=2023
        )

        params = resolver._build_search_query(citation)

        assert params is not None
        assert 'filter' in params
        assert 'Machine Learning Survey' in params['filter']
        assert '2022-2024' in params['filter']  # Year range

    def test_build_search_query_no_title(self):
        """Test query construction fails without title."""
        resolver = OpenAlexResolver()

        citation = Citation(year=2023)

        params = resolver._build_search_query(citation)

        assert params is None


class TestSemanticScholarAPIInitialization:
    """Test Semantic Scholar API client initialization."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(cache_dir=tmpdir)

            assert api.base_url == 'https://api.semanticscholar.org/graph/v1'
            assert api.timeout == 10
            assert api.enable_caching is True

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(
                api_key="test_key",
                cache_dir=tmpdir
            )

            assert api.api_key == "test_key"


class TestSemanticScholarAPICircuitBreaker:
    """Test Semantic Scholar API circuit breaker."""

    def test_circuit_breaker_opens_after_threshold(self):
        """Test that circuit breaker opens after threshold failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(
                circuit_breaker_threshold=3,
                cache_dir=tmpdir
            )

            # Record failures
            for _ in range(3):
                api._record_failure()

            # Circuit should be open
            assert api._circuit_open is True
            assert api._consecutive_failures == 3

    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(
                circuit_breaker_threshold=3,
                circuit_breaker_timeout=0.1,  # 100ms
                cache_dir=tmpdir
            )

            # Open circuit
            for _ in range(3):
                api._record_failure()

            assert api._circuit_open is True

            # Wait for timeout
            time.sleep(0.2)

            # Check circuit (should attempt recovery)
            is_open = api._check_circuit_breaker()

            assert is_open is False
            assert api._circuit_open is False

    def test_circuit_breaker_resets_on_success(self):
        """Test that circuit breaker resets on success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(cache_dir=tmpdir)

            # Record some failures
            api._record_failure()
            api._record_failure()

            assert api._consecutive_failures == 2

            # Record success
            api._record_success()

            assert api._consecutive_failures == 0


class TestSemanticScholarAPICaching:
    """Test Semantic Scholar API caching."""

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(cache_dir=tmpdir)

            # Initial stats
            stats = api.get_cache_stats()

            assert stats['cache_hits'] == 0
            assert stats['cache_misses'] == 0
            assert stats['cache_hit_rate'] == 0.0

    def test_persistent_cache_save_and_retrieve(self):
        """Test saving and retrieving from persistent cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            api = SemanticScholarAPI(cache_dir=tmpdir)

            cache_key = api._generate_cache_key('test/endpoint', {'param': 'value'})
            test_data = {'result': 'test'}

            # Save to cache
            api._save_to_persistent_cache(cache_key, 'test/endpoint', test_data)

            # Retrieve from cache
            cached = api._get_from_persistent_cache(cache_key)

            assert cached == test_data
