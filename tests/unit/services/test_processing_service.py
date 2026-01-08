"""Test suite for ProcessingService."""

import pytest
from unittest.mock import Mock
from pathlib import Path

from thoth.config import Config


class TestProcessingServiceInitialization:
    """Test ProcessingService initialization (requires pdf extras)."""

    def test_service_import_conditional(self):
        """Test ProcessingService import is conditional on pdf extras."""
        try:
            from thoth.services.processing_service import ProcessingService
            
            # If import succeeds, test initialization
            mock_llm = Mock()
            service = ProcessingService(llm_service=mock_llm)
            
            assert service.llm_service is mock_llm
            assert service.config is not None
        except ImportError:
            # PDF extras not installed - this is expected and OK
            pytest.skip("Processing service not available (pdf extras not installed)")


class TestProcessingServiceMethods:
    """Test ProcessingService key methods."""

    def test_service_has_required_methods(self):
        """Test ProcessingService has all required methods."""
        try:
            from thoth.services.processing_service import ProcessingService
            
            mock_llm = Mock()
            service = ProcessingService(llm_service=mock_llm)
            
            # Check key methods exist (actual methods from implementation)
            assert hasattr(service, 'ocr_convert')
            assert hasattr(service, 'process_pdf_to_markdown')
            assert hasattr(service, 'analyze_content')
            assert hasattr(service, 'extract_metadata')
            assert hasattr(service, 'get_processing_stats')
        except ImportError:
            pytest.skip("Processing service not available (pdf extras not installed)")

    def test_initialize_method(self):
        """Test initialize() method."""
        try:
            from thoth.services.processing_service import ProcessingService
            
            mock_llm = Mock()
            service = ProcessingService(llm_service=mock_llm)
            
            # Should not raise
            service.initialize()
        except ImportError:
            pytest.skip("Processing service not available (pdf extras not installed)")
