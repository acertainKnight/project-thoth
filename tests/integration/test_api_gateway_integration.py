"""
Integration tests for the API Gateway service with real configuration.
"""

import time
from unittest.mock import Mock, patch

import pytest

from thoth.services import ExternalAPIGateway, ServiceManager
from thoth.services.base import ServiceError
from thoth.utilities.config import APIGatewayConfig, ThothConfig


@pytest.fixture
def service_manager(thoth_config: ThothConfig):
    """Create a service manager for testing."""
    manager = ServiceManager(config=thoth_config)
    manager.initialize()
    return manager


def test_api_gateway_service_registration(service_manager: ServiceManager):
    """Test that the API Gateway is registered correctly in the ServiceManager."""
    gateway = service_manager.api_gateway
    assert gateway is not None
    assert isinstance(gateway, ExternalAPIGateway)
    assert 'test_service' in gateway.endpoints


def test_api_gateway_initialization(thoth_config: ThothConfig):
    """Test API gateway initialization with configuration."""
    gateway = ExternalAPIGateway(config=thoth_config)

    # Verify configuration is properly loaded
    assert gateway.rate_limiter is not None
    assert gateway.cache_expiry == 300  # Matches conftest.py setting
    assert gateway.default_timeout == 15  # Matches config default
    assert 'test_service' in gateway.endpoints
    assert gateway.endpoints['test_service'] == 'https://httpbin.org'

    # Initialize the service
    gateway.initialize()
    assert gateway._cache == {}


def test_api_gateway_url_building(thoth_config: ThothConfig):
    """Test URL building from service names and paths."""
    gateway = ExternalAPIGateway(config=thoth_config)

    # Test basic URL building
    url = gateway._build_url('test_service', '/get')
    assert url == 'https://httpbin.org/get'

    # Test with trailing slashes
    url = gateway._build_url('test_service', 'get')
    assert url == 'https://httpbin.org/get'

    # Test with empty path
    url = gateway._build_url('test_service', '')
    assert url == 'https://httpbin.org'

    # Test with unknown service
    with pytest.raises(Exception) as exc_info:
        gateway._build_url('unknown_service', '/path')
    assert 'Unknown service' in str(exc_info.value)


def test_api_gateway_cache_key_generation(thoth_config: ThothConfig):
    """Test cache key generation consistency."""
    gateway = ExternalAPIGateway(config=thoth_config)

    # Test consistent key generation
    key1 = gateway._cache_key('GET', 'https://example.com', {'q': 'test'}, None)
    key2 = gateway._cache_key('GET', 'https://example.com', {'q': 'test'}, None)
    assert key1 == key2
    assert len(key1) == 64  # SHA256 hex digest length

    # Test different parameters produce different keys
    key3 = gateway._cache_key('POST', 'https://example.com', {'q': 'test'}, None)
    assert key1 != key3


@patch('requests.Session.request')
def test_api_gateway_request_with_caching(mock_request, thoth_config: ThothConfig):
    """Test API gateway request method with caching behavior."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'test': 'data'}
    mock_request.return_value = mock_response

    gateway = ExternalAPIGateway(config=thoth_config)
    gateway.initialize()

    # First request
    result1 = gateway.get('test_service', '/get', params={'q': 'test'})
    assert result1 == {'test': 'data'}
    assert mock_request.call_count == 1

    # Second identical request should use cache
    result2 = gateway.get('test_service', '/get', params={'q': 'test'})
    assert result2 == {'test': 'data'}
    assert mock_request.call_count == 1  # No additional call

    # Different request should make new call
    result3 = gateway.get('test_service', '/different', params={'q': 'test'})
    assert result3 == {'test': 'data'}
    assert mock_request.call_count == 2


@patch('requests.Session.request')
def test_api_gateway_retry_logic(mock_request, thoth_config: ThothConfig):
    """Test API gateway retry logic for failed requests."""
    # Mock server error then success
    error_response = Mock()
    error_response.status_code = 500
    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {'retry': 'success'}

    mock_request.side_effect = [error_response, success_response]

    gateway = ExternalAPIGateway(config=thoth_config)
    gateway.initialize()

    # Patch sleep and rate limiter to avoid any timing issues
    with (
        patch('thoth.services.api_gateway.time.sleep'),
        patch.object(gateway.rate_limiter, 'acquire'),
    ):
        result = gateway.get('test_service', '/retry-test')
        assert result == {'retry': 'success'}
        assert mock_request.call_count == 2


def test_api_gateway_cache_management(thoth_config: ThothConfig):
    """Test cache clearing functionality."""
    gateway = ExternalAPIGateway(config=thoth_config)
    gateway.initialize()

    # Manually add cache entry
    cache_key = gateway._cache_key('GET', 'https://example.com', None, None)
    gateway._cache[cache_key] = (time.time(), {'cached': 'data'})

    assert len(gateway._cache) == 1

    # Clear cache
    gateway.clear_cache()
    assert len(gateway._cache) == 0


@patch('requests.Session.request')
def test_api_gateway_error_handling(mock_request, thoth_config: ThothConfig):
    """Test API gateway error handling for various failure scenarios."""
    # Mock network error
    mock_request.side_effect = Exception('Network error')

    gateway = ExternalAPIGateway(config=thoth_config)
    gateway.initialize()

    with pytest.raises(ServiceError):
        gateway.get('test_service', '/error-test')


def test_api_gateway_configuration_validation():
    """Test that API gateway properly validates configuration."""
    # Test with minimal valid configuration
    config = Mock(spec=ThothConfig)
    config.api_gateway_config = APIGatewayConfig(
        rate_limit=1.0,
        cache_expiry=300,
        default_timeout=10,
        endpoints={'service': 'https://example.com'},
    )

    gateway = ExternalAPIGateway(config=config)
    assert gateway.rate_limiter is not None
    assert gateway.default_timeout == 10
    assert gateway.cache_expiry == 300


@patch('requests.Session.request')
def test_api_gateway_convenience_methods(mock_request, thoth_config: ThothConfig):
    """Test GET and POST convenience methods."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'method': 'test'}
    mock_request.return_value = mock_response

    gateway = ExternalAPIGateway(config=thoth_config)
    gateway.initialize()

    # Test GET method
    result = gateway.get('test_service', '/get', params={'param': 'value'})
    assert result == {'method': 'test'}

    # Test POST method
    result = gateway.post('test_service', '/post', data={'key': 'value'})
    assert result == {'method': 'test'}

    # Verify correct HTTP methods were used
    calls = mock_request.call_args_list
    assert calls[0][0][0] == 'GET'  # First call was GET
    assert calls[1][0][0] == 'POST'  # Second call was POST


def test_api_gateway_caching(service_manager: ServiceManager):
    """Test the caching mechanism of the API Gateway."""
    gateway = service_manager.api_gateway

    # Use a real external service that is unlikely to change quickly
    service = 'mock_api'
    path = 'users/1'

    # Clear cache before starting
    gateway.clear_cache()

    # First call - should hit the network
    start_time = time.time()
    first_response = gateway.get(service, path)
    first_duration = time.time() - start_time
    assert first_response is not None
    assert first_response.get('id') == 1

    # Second call - should be cached and much faster
    start_time = time.time()
    second_response = gateway.get(service, path)
    second_duration = time.time() - start_time
    assert second_response == first_response
    assert second_duration < first_duration * 0.5, (
        'Cached response should be significantly faster'
    )


def test_api_gateway_retry_logic_with_service_manager(
    service_manager: ServiceManager, monkeypatch
):
    """Test the retry logic for server errors using service manager."""
    gateway = service_manager.api_gateway

    mock_response_503 = Mock()
    mock_response_503.status_code = 503
    mock_response_503.raise_for_status.side_effect = Exception('Service Unavailable')

    mock_response_200 = Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {'status': 'ok'}

    # Simulate failure on first two attempts, success on the third
    mock_session = Mock()
    mock_session.request.side_effect = [
        mock_response_503,
        mock_response_503,
        mock_response_200,
    ]

    monkeypatch.setattr(gateway, 'session', mock_session)

    response = gateway.get('test_service', 'status/200')

    assert response == {'status': 'ok'}
    assert mock_session.request.call_count == 3


def test_api_gateway_service_manager_integration(service_manager: ServiceManager):
    """Test using the API Gateway via the ServiceManager."""
    gateway = service_manager.get_service('api_gateway')
    assert gateway is not None

    response = gateway.get('test_service', 'get?arg=thoth')
    assert response is not None
    assert response.get('args') == {'arg': 'thoth'}
