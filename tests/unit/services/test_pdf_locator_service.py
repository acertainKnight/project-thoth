"""Test suite for PdfLocatorService."""

import pytest
from unittest.mock import Mock

from thoth.services.pdf_locator_service import PdfLocatorService
from thoth.config import Config


class TestPdfLocatorServiceInitialization:
    """Test PdfLocatorService initialization."""

    def test_initialization(self):
        """Test PdfLocatorService initializes correctly."""
        service = PdfLocatorService()
        
        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test PdfLocatorService accepts custom config."""
        mock_config = Mock(spec=Config)
        service = PdfLocatorService(config=mock_config)
        
        assert service.config is mock_config


class TestPdfLocatorServiceMethods:
    """Test PdfLocatorService key methods."""

    def test_service_has_required_methods(self):
        """Test PdfLocatorService has all required methods."""
        service = PdfLocatorService()
        
        # Check key methods exist (actual methods from implementation)
        assert hasattr(service, 'locate')
        assert hasattr(service, 'health_check')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = PdfLocatorService()
        
        # Should not raise
        service.initialize()
