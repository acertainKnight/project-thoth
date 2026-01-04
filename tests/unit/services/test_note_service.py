"""Test suite for NoteService."""

import pytest
from unittest.mock import Mock
from pathlib import Path

from thoth.services.note_service import NoteService
from thoth.config import Config


class TestNoteServiceInitialization:
    """Test NoteService initialization."""

    def test_initialization(self):
        """Test NoteService initializes correctly."""
        service = NoteService()
        
        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test NoteService accepts custom config."""
        mock_config = Mock(spec=Config)
        service = NoteService(config=mock_config)
        
        assert service.config is mock_config


class TestNoteServiceMethods:
    """Test NoteService key methods."""

    def test_service_has_required_methods(self):
        """Test NoteService has all required methods."""
        service = NoteService()
        
        # Check key methods exist
        assert hasattr(service, 'create_note')
        assert hasattr(service, 'read_note')
        assert hasattr(service, 'update_note')
        assert hasattr(service, 'delete_note')
        assert hasattr(service, 'list_notes')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = NoteService()
        
        # Should not raise
        service.initialize()
