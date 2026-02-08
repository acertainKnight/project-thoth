"""Test suite for NoteService."""

from unittest.mock import Mock

import pytest

from thoth.services.note_service import NoteService


class TestNoteServiceInitialization:
    """Test NoteService initialization."""

    def test_initialization(self):
        """Test NoteService initializes correctly."""
        service = NoteService()

        assert service.config is not None

    @pytest.mark.skip(
        reason='Complex service dependencies - better for integration tests'
    )
    def test_initialization_with_custom_config(self):
        """Test NoteService accepts custom config."""
        mock_config = Mock()  # Don't use spec to allow any attributes
        service = NoteService(config=mock_config)

        assert service.config is mock_config


class TestNoteServiceMethods:
    """Test NoteService key methods."""

    def test_service_has_required_methods(self):
        """Test NoteService has all required methods."""
        service = NoteService()

        # Check key methods exist (actual methods from implementation)
        assert hasattr(service, 'create_note')
        assert hasattr(service, 'create_basic_note')
        assert hasattr(service, 'get_note_statistics')
        assert hasattr(service, 'health_check')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = NoteService()

        # Should not raise
        service.initialize()
