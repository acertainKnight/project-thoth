"""
Test suite for ServiceManager.

Tests service initialization, dependency injection, lazy loading,
and dynamic service access patterns.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from thoth.services.service_manager import ServiceManager
from thoth.config import Config


class TestServiceManagerInitialization:
    """Test ServiceManager initialization and service creation."""

    def test_initialization_creates_empty_manager(self):
        """Test ServiceManager initializes without creating services."""
        manager = ServiceManager()
        
        assert manager._initialized is False
        assert manager._services == {}
        assert manager.config is not None

    def test_initialization_with_custom_config(self):
        """Test ServiceManager accepts custom config."""
        custom_config = Mock(spec=Config)
        manager = ServiceManager(config=custom_config)
        
        assert manager.config is custom_config

    def test_lazy_initialization(self):
        """Test services are not initialized until first access."""
        manager = ServiceManager()
        
        # Services should not be initialized yet
        assert manager._initialized is False
        assert len(manager._services) == 0
        
        # Accessing a service should trigger initialization
        _ = manager.llm
        
        assert manager._initialized is True
        assert len(manager._services) > 0

    def test_double_initialization_prevented(self):
        """Test initialize() is idempotent (safe to call multiple times)."""
        manager = ServiceManager()
        
        # First initialization
        manager.initialize()
        services_after_first = manager._services.copy()
        first_llm_instance = manager._services['llm']
        
        # Second initialization should not recreate services
        manager.initialize()
        services_after_second = manager._services
        second_llm_instance = manager._services['llm']
        
        # Same services, same instances
        assert services_after_first.keys() == services_after_second.keys()
        assert first_llm_instance is second_llm_instance

    def test_all_required_services_created(self):
        """Test all required services are initialized."""
        manager = ServiceManager()
        manager.initialize()
        
        # Core required services (always present)
        required_services = [
            'llm',
            'article',
            'note',
            'query',
            'discovery',
            'web_search',
            'pdf_locator',
            'api_gateway',
            'postgres',
            'research_question',
            'tag',
            'discovery_manager',
            'discovery_orchestrator',
        ]
        
        for service_name in required_services:
            assert service_name in manager._services, f"Service '{service_name}' not created"
            assert manager._services[service_name] is not None, f"Service '{service_name}' is None"


class TestServiceManagerOptionalServices:
    """Test optional service handling (services requiring extra dependencies)."""

    def test_optional_services_handle_missing_extras(self):
        """Test optional services are None when extras not installed."""
        manager = ServiceManager()
        manager.initialize()
        
        # Optional services (may be None if extras not installed)
        # Note: letta removed - agents use native Letta REST API (port 8283)
        optional_services = ['processing', 'rag']
        
        for service_name in optional_services:
            assert service_name in manager._services, f"Optional service '{service_name}' not in _services"
            # Value can be None or an instance, both are valid
            service = manager._services.get(service_name)
            assert service is None or hasattr(service, '__class__')

    @patch('thoth.services.service_manager.PROCESSING_AVAILABLE', False)
    def test_processing_service_none_when_unavailable(self):
        """Test processing service is None when pdf extras not installed."""
        manager = ServiceManager()
        manager.initialize()
        
        assert manager._services['processing'] is None

    @patch('thoth.services.service_manager.RAG_AVAILABLE', False)
    def test_rag_service_none_when_unavailable(self):
        """Test RAG service is None when embeddings extras not installed."""
        manager = ServiceManager()
        manager.initialize()
        
        assert manager._services['rag'] is None

    # Note: test_letta_service_none_when_unavailable removed
    # LettaService deleted - agents use native Letta REST API (port 8283)


class TestServiceManagerDynamicAccess:
    """Test dynamic service access via __getattr__."""

    def test_dynamic_attribute_access(self):
        """Test services can be accessed via dot notation."""
        manager = ServiceManager()
        
        # Access via dot notation should work
        llm_service = manager.llm
        article_service = manager.article
        
        assert llm_service is not None
        assert article_service is not None
        assert llm_service is manager._services['llm']
        assert article_service is manager._services['article']

    def test_dynamic_access_triggers_initialization(self):
        """Test accessing service via dot notation triggers lazy init."""
        manager = ServiceManager()
        
        assert manager._initialized is False
        
        _ = manager.llm
        
        assert manager._initialized is True

    def test_nonexistent_service_raises_attribute_error(self):
        """Test accessing non-existent service raises AttributeError."""
        manager = ServiceManager()
        manager.initialize()
        
        with pytest.raises(AttributeError) as exc_info:
            _ = manager.nonexistent_service
        
        assert "has no service 'nonexistent_service'" in str(exc_info.value)
        assert "Available services:" in str(exc_info.value)

    def test_service_lookup_by_name(self):
        """Test get_service() method for explicit service lookup."""
        manager = ServiceManager()
        manager.initialize()
        
        llm_service = manager.get_service('llm')
        
        assert llm_service is not None
        assert llm_service is manager._services['llm']

    def test_get_service_nonexistent_raises_key_error(self):
        """Test get_service() raises KeyError for non-existent service."""
        manager = ServiceManager()
        manager.initialize()
        
        with pytest.raises(KeyError) as exc_info:
            manager.get_service('nonexistent_service')
        
        assert "Service 'nonexistent_service' not found" in str(exc_info.value)


class TestServiceManagerUtilityMethods:
    """Test utility methods like set_citation_tracker, get_all_services, etc."""

    def test_set_citation_tracker(self):
        """Test citation tracker can be set on services."""
        manager = ServiceManager()
        manager.initialize()
        
        mock_tracker = Mock()
        mock_tracker.graph.nodes = []
        
        # Should not raise
        manager.set_citation_tracker(mock_tracker)
        
        # TagService should have tracker set (if available)
        if manager._services['tag'] is not None:
            assert hasattr(manager._services['tag'], '_citation_tracker')

    def test_get_all_services(self):
        """Test get_all_services() returns all initialized services."""
        manager = ServiceManager()
        manager.initialize()
        
        all_services = manager.get_all_services()
        
        assert isinstance(all_services, dict)
        assert len(all_services) > 0
        assert all_services.keys() == manager._services.keys()
        # Should be a copy, not the original
        assert all_services is not manager._services

    def test_shutdown_clears_services(self):
        """Test shutdown() clears all services and resets state."""
        manager = ServiceManager()
        manager.initialize()
        
        assert manager._initialized is True
        assert len(manager._services) > 0
        
        manager.shutdown()
        
        assert manager._initialized is False
        assert len(manager._services) == 0

    def test_set_filter_function(self):
        """Test filter function can be set on discovery service."""
        manager = ServiceManager()
        manager.initialize()
        
        mock_filter = Mock()
        
        # Should not raise
        manager.set_filter_function(mock_filter)
        
        assert manager._services['discovery'].filter_func is mock_filter


class TestServiceManagerCoverage:
    """Additional tests for edge cases and coverage."""

    def test_ensure_initialized_is_idempotent(self):
        """Test _ensure_initialized() can be called multiple times safely."""
        manager = ServiceManager()
        
        manager._ensure_initialized()
        first_services = manager._services.copy()
        
        manager._ensure_initialized()
        second_services = manager._services
        
        assert first_services.keys() == second_services.keys()

    def test_manager_can_be_created_multiple_times(self):
        """Test multiple ServiceManager instances can coexist."""
        manager1 = ServiceManager()
        manager2 = ServiceManager()
        
        manager1.initialize()
        manager2.initialize()
        
        # Different instances
        assert manager1 is not manager2
        assert manager1._services is not manager2._services
        
        # But both have services
        assert len(manager1._services) > 0
        assert len(manager2._services) > 0
