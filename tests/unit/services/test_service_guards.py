"""Tests for optional service guards in ServiceManager."""

import pytest

from thoth.services.service_manager import ServiceManager, ServiceUnavailableError


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError exception."""

    def test_exception_can_be_raised(self):
        """Test that ServiceUnavailableError can be raised."""
        with pytest.raises(ServiceUnavailableError) as exc_info:
            raise ServiceUnavailableError('Test error message')

        assert 'Test error message' in str(exc_info.value)

    def test_exception_is_exception_subclass(self):
        """Test that ServiceUnavailableError is an Exception."""
        assert issubclass(ServiceUnavailableError, Exception)


class TestRequireService:
    """Tests for ServiceManager.require_service() method."""

    def test_require_service_returns_available_service(self):
        """Test that require_service returns the service when available."""
        manager = ServiceManager()
        manager.initialize()

        # Test with a core service that's always available
        llm_service = manager.require_service('llm', 'core')

        assert llm_service is not None
        assert llm_service is manager.llm

    def test_require_service_raises_for_unavailable_service(self):
        """Test that require_service raises ServiceUnavailableError for None services."""
        manager = ServiceManager()
        manager.initialize()

        # Mock a service to be None (simulating missing extras)
        manager._services['processing'] = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            manager.require_service('processing', 'pdf')

        error_msg = str(exc_info.value)
        assert 'processing' in error_msg
        assert 'not available' in error_msg
        assert 'uv sync --extra pdf' in error_msg

    def test_require_service_with_different_extras(self):
        """Test error messages with different extras names."""
        manager = ServiceManager()
        manager.initialize()

        # Set RAG to None
        manager._services['rag'] = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            manager.require_service('rag', 'embeddings')

        error_msg = str(exc_info.value)
        assert 'rag' in error_msg
        assert 'uv sync --extra embeddings' in error_msg

    def test_require_service_multiple_calls(self):
        """Test that require_service can be called multiple times."""
        manager = ServiceManager()
        manager.initialize()

        # Should work multiple times
        llm1 = manager.require_service('llm', 'core')
        llm2 = manager.require_service('llm', 'core')

        assert llm1 is llm2  # Same instance


class TestOptionalServiceAccess:
    """Tests for accessing optional services via __getattr__."""

    def test_accessing_none_service_raises_helpful_error(self):
        """Test that accessing a None service raises ServiceUnavailableError."""
        manager = ServiceManager()
        manager.initialize()

        # Mock processing service as None
        manager._services['processing'] = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            _ = manager.processing

        error_msg = str(exc_info.value)
        assert 'processing' in error_msg
        assert 'not available' in error_msg
        assert 'uv sync --extra pdf' in error_msg

    def test_accessing_none_rag_service(self):
        """Test error message for RAG service."""
        manager = ServiceManager()
        manager.initialize()

        manager._services['rag'] = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            _ = manager.rag

        error_msg = str(exc_info.value)
        assert 'rag' in error_msg
        assert 'uv sync --extra embeddings' in error_msg

    def test_accessing_none_cache_service(self):
        """Test error message for cache service."""
        manager = ServiceManager()
        manager.initialize()

        manager._services['cache'] = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            _ = manager.cache

        error_msg = str(exc_info.value)
        assert 'cache' in error_msg
        assert 'uv sync --extra optimization' in error_msg

    def test_accessing_none_async_processing_service(self):
        """Test error message for async_processing service."""
        manager = ServiceManager()
        manager.initialize()

        manager._services['async_processing'] = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            _ = manager.async_processing

        error_msg = str(exc_info.value)
        assert 'async_processing' in error_msg
        assert 'uv sync --extra optimization' in error_msg

    def test_accessing_available_optional_service_works(self):
        """Test that accessing an available optional service works normally."""
        manager = ServiceManager()
        manager.initialize()

        # If processing service is available, this should work
        if manager._services.get('processing') is not None:
            processing = manager.processing
            assert processing is not None

    def test_nonexistent_service_raises_attribute_error(self):
        """Test that accessing a non-existent service raises AttributeError."""
        manager = ServiceManager()
        manager.initialize()

        with pytest.raises(AttributeError) as exc_info:
            _ = manager.nonexistent_service

        error_msg = str(exc_info.value)
        assert 'nonexistent_service' in error_msg
        assert 'Available services' in error_msg


class TestServiceGuardsIntegration:
    """Integration tests for service guards."""

    def test_guard_provides_better_error_than_none_attribute(self):
        """Test that guards provide better errors than accessing None.attribute."""
        manager = ServiceManager()
        manager.initialize()

        # Set RAG to None
        manager._services['rag'] = None

        # Without guard, this would be:
        # AttributeError: 'NoneType' object has no attribute 'search'

        # With guard via __getattr__:
        with pytest.raises(ServiceUnavailableError) as exc_info:
            _ = manager.rag.search('query')  # Accessing rag triggers the guard

        # Error message is helpful
        error_msg = str(exc_info.value)
        assert 'rag' in error_msg
        assert 'not available' in error_msg
        assert 'uv sync' in error_msg

    def test_require_service_pattern_in_code(self):
        """Test the recommended pattern using require_service."""
        manager = ServiceManager()
        manager.initialize()

        # This is the recommended pattern for optional services
        try:
            rag = manager.require_service('rag', 'embeddings')
            # Use the service
            # results = rag.search(query)
        except ServiceUnavailableError:
            # Handle gracefully - service not available
            pass

    def test_all_optional_services_have_extras_mapping(self):
        """Test that all optional services have extras mappings in __getattr__."""
        manager = ServiceManager()
        manager.initialize()

        # These services should have extras mappings
        optional_services = ['processing', 'rag', 'cache', 'async_processing']

        for service_name in optional_services:
            # Set service to None
            manager._services[service_name] = None

            # Try to access it
            try:
                _ = getattr(manager, service_name)
                pytest.fail(
                    f'Should have raised ServiceUnavailableError for {service_name}'
                )
            except ServiceUnavailableError as e:
                # Should contain extras installation command
                error_msg = str(e)
                assert 'uv sync --extra' in error_msg, (
                    f'Missing extras command for {service_name}'
                )


class TestBackwardCompatibility:
    """Tests to ensure changes don't break existing code."""

    def test_existing_service_access_still_works(self):
        """Test that normal service access still works."""
        manager = ServiceManager()
        manager.initialize()

        # All of these should work
        assert manager.llm is not None
        assert manager.article is not None
        assert manager.note is not None
        assert manager.discovery is not None

    def test_get_service_method_still_works(self):
        """Test that get_service() method still works."""
        manager = ServiceManager()
        manager.initialize()

        llm = manager.get_service('llm')
        assert llm is not None
        assert llm is manager.llm
